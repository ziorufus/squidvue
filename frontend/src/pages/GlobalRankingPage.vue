<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'

const router = useRouter()

const ranking = ref([])
const lastUpdated = ref('')
const loading = ref(true)
let timerId = null

async function fetchGlobalRanking() {
  const { data } = await api.get('/api/public/ranking/global')
  ranking.value = data.global || []
  lastUpdated.value = new Date().toLocaleTimeString()
  loading.value = false
}

onMounted(async () => {
  await fetchGlobalRanking()
  timerId = setInterval(fetchGlobalRanking, 5000)
})

onBeforeUnmount(() => {
  if (timerId) clearInterval(timerId)
})
</script>

<template>
  <div class="container-fluid py-4 px-4 px-md-5">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h2 mb-0">Global Ranking</h1>
      <div class="d-flex gap-2 align-items-center">
        <small class="text-muted">Updated: {{ lastUpdated || '-' }}</small>
        <button class="btn btn-outline-secondary" @click="router.push('/admin')">Back</button>
      </div>
    </div>

    <div class="card card-soft p-4">
      <div v-if="loading">Loading ranking...</div>
      <div v-else-if="ranking.length === 0">No results yet.</div>
      <ol v-else class="fs-4 m-0 ps-4">
        <li v-for="(row, i) in ranking" :key="`${row.emoji}-${i}`" class="py-1 d-flex justify-content-between">
          <span>{{ row.emoji }}</span>
          <strong>{{ Number(row.score || 0).toFixed(2) }}</strong>
        </li>
      </ol>
    </div>
  </div>
</template>
