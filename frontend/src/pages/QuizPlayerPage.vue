<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { connectQuizSocket } from '../services/ws'

const route = useRoute()
const router = useRouter()
const code = computed(() => String(route.params.code || '').toUpperCase())

const quiz = ref(null)
const participant = ref(null)
const state = ref({ phase: 'idle', remaining_seconds: 0, question: null, question_index: null, total_questions: 0 })
const ws = ref(null)
const chosen = ref('')
const openAnswer = ref('')
const submitted = ref(false)
const desktop = ref(window.innerWidth >= 768)
const ack = ref('')
const lastStateKey = ref('')

function resetAnswerUi() {
  chosen.value = ''
  openAnswer.value = ''
  submitted.value = false
  ack.value = ''
}

function onResize() {
  desktop.value = window.innerWidth >= 768
}

async function loadInfo() {
  const { data } = await api.get(`/api/public/quiz/${code.value}`)
  quiz.value = data.quiz
  participant.value = data.participant
}

async function refreshParticipantScore() {
  if (!participant.value) return
  const { data } = await api.get(`/api/public/quiz/${code.value}`)
  participant.value = {
    ...participant.value,
    score: data.participant.score
  }
}

function connect() {
  ws.value = connectQuizSocket(code.value, 'student', async (msg, socket) => {
    try {
    if (msg.type === 'state') {
      const stateKey = `${msg.phase}:${msg.question_index ?? -1}`
      const previousKey = lastStateKey.value
      state.value = msg
      lastStateKey.value = stateKey

      if (previousKey && previousKey !== stateKey) {
        await refreshParticipantScore()
      }

      if (previousKey !== stateKey || msg.phase !== 'question') {
        resetAnswerUi()
      }
    }
    if (msg.type === 'answer_ack') {
      submitted.value = msg.accepted || submitted.value
      ack.value = msg.accepted ? 'Answer received' : `Not accepted: ${msg.reason}`
      if (msg.accepted && participant.value) {
        participant.value = {
          ...participant.value,
          score: Number(participant.value.score || 0) + Number(msg.score || 0)
        }
      }
    }
    } catch {
      // keep socket alive even if a transient refresh request fails
    }
  }, (socket) => {
    socket.send(JSON.stringify({ action: 'ping' }))
  })
}

function submitChoice(letter) {
  if (!state.value.question || submitted.value || state.value.phase !== 'question') return
  chosen.value = letter
  submitted.value = true
  ws.value?.send(JSON.stringify({
    action: 'submit_answer',
    question_id: state.value.question.id,
    value: letter
  }))
}

function saveDraft() {
  if (!state.value.question || state.value.question.question_type !== 'open') return
  ws.value?.send(JSON.stringify({
    action: 'save_open_draft',
    question_id: state.value.question.id,
    value: openAnswer.value
  }))
}

function submitOpen(event) {
  if (!state.value.question || submitted.value || state.value.phase !== 'question') return
  event?.currentTarget?.blur?.()
  submitted.value = true
  ws.value?.send(JSON.stringify({
    action: 'submit_answer',
    question_id: state.value.question.id,
    value: openAnswer.value
  }))
}

watch(openAnswer, saveDraft)

onMounted(async () => {
  window.addEventListener('resize', onResize)
  try {
    await loadInfo()
    connect()
  } catch {
    router.push('/')
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (ws.value) ws.value.close()
})
</script>

<template>
  <div class="container py-4 quiz-player-page">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h4 mb-0">Quiz {{ code }}</h1>
      <button class="btn btn-outline-secondary btn-sm" @click="router.push('/')">Home</button>
    </div>

    <div class="card card-soft p-3 mb-3" v-if="participant && !['countdown', 'question'].includes(state.phase)">
      <div class="fs-2">{{ participant.emoji }}</div>
      <div>Your score: {{ participant.score.toFixed(2) }}</div>
      <div>Phase: {{ state.phase }}</div>
    </div>

    <div class="alert alert-warning d-none d-md-block">
      This interface is designed for phones/tablets. Resize below the `md` breakpoint to answer questions.
    </div>

    <div class="d-md-none">
      <div v-if="state.phase === 'countdown'" class="card card-soft p-4 text-center">
        <div class="display-3">{{ participant?.emoji }}</div>
        <div class="display-4">{{ state.remaining_seconds }}</div>
      </div>

      <div v-else-if="state.phase === 'question' && state.question" class="card card-soft p-3">
        <div class="d-flex justify-content-between mb-2">
          <div class="fs-3">{{ participant?.emoji }}</div>
          <div>Q {{ (state.question_index ?? 0) + 1 }}/{{ state.total_questions }}</div>
        </div>
        <div class="mb-3">Time left: {{ state.remaining_seconds }}s</div>

        <div v-if="state.question.question_type === 'multiple_choice'" class="d-grid gap-2">
          <button
            v-for="letter in ['A','B','C','D','E']"
            :key="letter"
            class="btn btn-outline-dark question-btn"
            :class="{ active: chosen === letter }"
            :disabled="submitted"
            @click="submitChoice(letter)"
          >
            {{ letter }}
          </button>
        </div>

        <div v-else>
          <input
            v-model="openAnswer"
            class="form-control mb-2"
            placeholder="Type answer"
            :disabled="submitted"
            autofocus
          />
          <button class="btn btn-primary w-100" :disabled="submitted" @click="submitOpen($event)">Confirm</button>
        </div>

        <div class="mt-2 small">{{ ack }}</div>
      </div>

      <div v-else class="card card-soft p-3">
        <div class="fs-2 mb-2">{{ participant?.emoji }}</div>
        <div>Waiting for the teacher to start the quiz.</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.quiz-player-page .btn:hover {
  color: inherit;
  background-color: inherit;
  border-color: inherit;
}
</style>
