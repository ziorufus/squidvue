<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../services/api'

const route = useRoute()
const router = useRouter()
const quizId = route.params.quiz_id

const quiz = ref(null)
const questions = ref([])
const participantsCount = ref(0)
const loading = ref(true)
const error = ref('')

async function fetchDetail() {
  try {
    const { data } = await api.get(`/api/quizzes/${quizId}/detail`)
    quiz.value = data.quiz
    questions.value = data.questions
    participantsCount.value = data.participants_count
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Errore nel caricamento'
  } finally {
    loading.value = false
  }
}

onMounted(fetchDetail)
</script>

<template>
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
      <div>
        <h1 class="h3 mb-0">{{ quiz?.title || 'Dettaglio Quiz' }}</h1>
        <small class="text-muted" v-if="quiz">
          Codice: <strong>{{ quiz.code }}</strong> &middot;
          Stato: <strong>{{ quiz.status }}</strong> &middot;
          Partecipanti: <strong>{{ participantsCount }}</strong>
        </small>
      </div>
      <button class="btn btn-outline-secondary" @click="router.push('/admin')">Admin</button>
    </div>

    <div v-if="loading" class="text-muted">Caricamento...</div>
    <div v-else-if="error" class="alert alert-danger">{{ error }}</div>
    <div v-else-if="questions.length === 0" class="text-muted">Nessuna domanda.</div>

    <div v-for="q in questions" :key="q.id" class="card card-soft mb-4">
      <div class="card-header d-flex align-items-start gap-2">
        <span class="badge bg-secondary mt-1">{{ q.position }}</span>
        <div class="flex-grow-1">
          <span>{{ q.text }}</span>
          <span
            class="badge ms-2"
            :class="q.question_type === 'multiple_choice' ? 'bg-info text-dark' : 'bg-warning text-dark'"
          >
            {{ q.question_type === 'multiple_choice' ? 'Scelta multipla' : 'Aperta' }}
          </span>
        </div>
        <small class="text-muted text-nowrap">max {{ q.max_points }} pt</small>
      </div>

      <div class="card-body">

        <!-- SCELTA MULTIPLA -->
        <div v-if="q.question_type === 'multiple_choice'">
          <div
            v-for="choice in q.stats.choices"
            :key="choice.option"
            class="mb-2 p-2 rounded"
            :class="{
              'bg-success bg-opacity-10 border border-success': choice.is_correct,
              'bg-light': !choice.is_correct && choice.option !== 'no_answer',
              'bg-secondary bg-opacity-10': choice.option === 'no_answer',
            }"
          >
            <div class="d-flex align-items-center gap-2">
              <span
                class="badge"
                :class="{
                  'bg-success': choice.is_correct,
                  'bg-primary': !choice.is_correct && choice.option !== 'no_answer',
                  'bg-secondary': choice.option === 'no_answer',
                }"
              >{{ choice.option === 'no_answer' ? '—' : choice.option }}</span>
              <span :class="{ 'fw-semibold': choice.is_correct }">
                {{ choice.option === 'no_answer' ? 'Nessuna risposta' : choice.text }}
              </span>
              <span class="ms-auto badge bg-white text-dark border">{{ choice.count }}</span>
            </div>
            <div v-if="choice.emojis.length" class="mt-1 ms-4 fs-5 lh-1">
              {{ choice.emojis.join(' ') }}
            </div>
          </div>
        </div>

        <!-- APERTA -->
        <div v-else>
          <div v-if="q.stats.answers.length === 0" class="text-muted fst-italic">Nessuna risposta.</div>
          <table v-else class="table table-sm table-hover mb-0 align-middle">
            <thead class="table-light">
              <tr>
                <th>Risposta</th>
                <th class="text-center" style="width: 56px">N°</th>
                <th>Partecipanti</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ans in q.stats.answers" :key="ans.value ?? '__empty__'">
                <td>
                  <span
                    v-if="ans.value !== ''"
                    :class="{ 'fw-semibold text-success': ans.value.toLowerCase() === (q.correct_answer || '').toLowerCase() }"
                  >{{ ans.value }}</span>
                  <span v-else class="text-muted fst-italic">(vuota)</span>
                </td>
                <td class="text-center fw-bold">{{ ans.count }}</td>
                <td class="fs-5 lh-sm">{{ ans.emojis.join(' ') }}</td>
              </tr>
            </tbody>
          </table>
        </div>

      </div>
    </div>
  </div>
</template>
