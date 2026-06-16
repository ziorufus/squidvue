<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'
import { connectQuizSocket } from '../services/ws'

const route = useRoute()
const router = useRouter()
const code = computed(() => String(route.params.code || '').toUpperCase())

const state = ref(null)
const ranking = ref({ quiz: [], global: [] })
const ws = ref(null)

async function fetchRanking() {
  const { data } = await api.get(`/api/public/quiz/${code.value}/ranking`)
  ranking.value = data
}

onMounted(() => {
  ws.value = connectQuizSocket(code.value, 'screen', async (msg) => {
    if (msg.type !== 'state') return
    state.value = msg
    if (msg.phase === 'finished') {
      await fetchRanking()
    }
  })
})

onBeforeUnmount(() => {
  if (ws.value) ws.value.close()
})
</script>

<template>
  <div class="container-fluid py-4 px-5">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h2 mb-0">Question Screen {{ code }}</h1>
      <button class="btn btn-outline-secondary" @click="router.push('/admin')">Back</button>
    </div>

    <div v-if="!state" class="card card-soft p-4">Connecting...</div>

    <div v-else-if="state.phase === 'countdown'" class="card card-soft p-5 text-center">
      <h2 class="display-2">{{ state.remaining_seconds }}</h2>
      <p class="lead">Get ready</p>
    </div>

    <div v-else-if="state.phase === 'question' && state.question" class="card card-soft p-4">
      <div class="d-flex justify-content-between mb-2">
        <h2 class="h3 mb-0">Question {{ (state.question_index ?? 0) + 1 }}/{{ state.total_questions }}</h2>
        <div class="h3">{{ state.remaining_seconds }}s</div>
      </div>
      <p class="fs-4">{{ state.question.text }}</p>
      <div v-if="state.question.question_type === 'multiple_choice'" class="row g-2">
        <div v-for="letter in ['A','B','C','D','E']" :key="letter" class="col-12">
          <div class="border rounded p-3 bg-light"><strong>{{ letter }}</strong> {{ state.question.options[letter] }}</div>
        </div>
      </div>
      <div v-else class="alert alert-info">Open question</div>
    </div>

    <div v-else-if="state.phase === 'finished'" class="row g-3">
      <div class="col-md-6">
        <div class="card card-soft p-3">
          <h2 class="h5">Quiz Ranking</h2>
          <ol>
            <li v-for="r in ranking.quiz" :key="r.emoji">{{ r.emoji }} - {{ r.score.toFixed(2) }}</li>
          </ol>
        </div>
      </div>
      <div class="col-md-6">
        <div class="card card-soft p-3">
          <h2 class="h5">Global Ranking</h2>
          <ol>
            <li v-for="r in ranking.global" :key="r.emoji">{{ r.emoji }} - {{ r.score.toFixed(2) }}</li>
          </ol>
        </div>
      </div>
    </div>

    <div v-else class="card card-soft p-4">Quiz not started yet.</div>
  </div>
</template>
