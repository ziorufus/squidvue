<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import api from '../services/api'
import { clearSession, getUser } from '../services/auth'
import { connectQuizSocket } from '../services/ws'

const router = useRouter()
const me = getUser()
const quizzes = ref([])
const privileged = ref([])
const defaults = ref({ default_question_time: 20, default_countdown_time: 5, default_max_points: 1 })
const status = ref('')
const wsStats = ref(null)
const ws = ref(null)
const selectedQuiz = ref(null)
const privilegedEmail = ref('')

function blankQuestion(position) {
  return {
    position,
    text: '',
    question_type: 'multiple_choice',
    option_a: '',
    option_b: '',
    option_c: '',
    option_d: '',
    option_e: '',
    correct_answer: 'A',
    max_points: defaults.value.default_max_points
  }
}

const form = reactive({
  id: null,
  title: '',
  question_time: 20,
  countdown_time: 5,
  questions: [blankQuestion(1)]
})

function resetForm() {
  form.id = null
  form.title = ''
  form.question_time = defaults.value.default_question_time
  form.countdown_time = defaults.value.default_countdown_time
  form.questions = [blankQuestion(1)]
}

function addQuestion() {
  form.questions.push(blankQuestion(form.questions.length + 1))
}

function removeQuestion(index) {
  form.questions.splice(index, 1)
  form.questions.forEach((q, i) => { q.position = i + 1 })
}

async function loadAll() {
  try {
    const [q, d] = await Promise.all([
      api.get('/api/quizzes'),
      api.get('/api/quizzes/defaults')
    ])
    quizzes.value = q.data
    defaults.value = d.data
    if (me.role === 'admin') {
      const p = await api.get('/api/users/privileged')
      privileged.value = p.data
    }
  } catch (error) {
    if (error?.response?.status === 401) {
      clearSession()
      router.push('/')
      return
    }
    throw error
  }
}

function pickQuiz(quiz) {
  selectedQuiz.value = quiz
  if (ws.value) ws.value.close()
  ws.value = connectQuizSocket(quiz.code, 'admin', (msg) => {
    if (msg.type === 'state') wsStats.value = msg
  })
}

async function saveQuiz() {
  status.value = ''
  const payload = {
    ...form,
    questions: form.questions.map((q, i) => ({ ...q, position: i + 1 }))
  }
  if (form.id) {
    await api.put(`/api/quizzes/${form.id}`, payload)
    status.value = 'Quiz updated'
  } else {
    await api.post('/api/quizzes', payload)
    status.value = 'Quiz created'
  }
  await loadAll()
  resetForm()
}

async function editQuiz(code) {
  const { data } = await api.get(`/api/quizzes/code/${code}`)
  form.id = data.id
  form.title = data.title
  form.question_time = data.question_time
  form.countdown_time = data.countdown_time
  form.questions = data.questions
}

async function removeQuiz(id) {
  await api.delete(`/api/quizzes/${id}`)
  await loadAll()
}

async function startQuiz(id) {
  await api.post(`/api/quizzes/${id}/start`)
  await loadAll()
}

async function stopQuiz(id) {
  await api.post(`/api/quizzes/${id}/stop`)
  await loadAll()
}

async function resetQuiz(id) {
  await api.post(`/api/quizzes/${id}/reset`)
  await loadAll()
}

async function addPrivileged() {
  if (!privilegedEmail.value.trim()) return
  await api.post('/api/users/privileged', { email: privilegedEmail.value })
  privilegedEmail.value = ''
  const p = await api.get('/api/users/privileged')
  privileged.value = p.data
}

async function deletePrivileged(id) {
  await api.delete(`/api/users/privileged/${id}`)
  const p = await api.get('/api/users/privileged')
  privileged.value = p.data
}

onMounted(async () => {
  await loadAll()
  resetForm()
})

onBeforeUnmount(() => {
  if (ws.value) ws.value.close()
})
</script>

<template>
  <div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-3">
      <h1 class="h3 mb-0">Admin Panel</h1>
      <div class="d-flex gap-2">
        <button class="btn btn-outline-secondary" @click="router.push('/')">Home</button>
      </div>
    </div>

    <div class="row g-4">
      <div class="col-lg-8">
        <div class="card card-soft p-3">
          <h2 class="h5">Create or Edit Quiz</h2>
          <div class="row g-2">
            <div class="col-md-6">
              <label class="form-label">Title</label>
              <input v-model="form.title" class="form-control" />
            </div>
            <div class="col-md-3">
              <label class="form-label">Question Time</label>
              <input v-model.number="form.question_time" type="number" min="1" class="form-control" />
            </div>
            <div class="col-md-3">
              <label class="form-label">Countdown</label>
              <input v-model.number="form.countdown_time" type="number" min="1" class="form-control" />
            </div>
          </div>

          <hr />
          <h3 class="h6">Questions</h3>
          <div v-for="(q, idx) in form.questions" :key="idx" class="border rounded p-2 mb-2 bg-light">
            <div class="d-flex justify-content-between align-items-center mb-2">
              <strong>Question {{ idx + 1 }}</strong>
              <button class="btn btn-sm btn-outline-danger" @click="removeQuestion(idx)">Remove</button>
            </div>
            <textarea v-model="q.text" class="form-control mb-2" rows="2" placeholder="Question text" />
            <div class="row g-2 mb-2">
              <div class="col-md-4">
                <select v-model="q.question_type" class="form-select">
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="open">Open</option>
                </select>
              </div>
              <div class="col-md-4">
                <input v-model.number="q.max_points" type="number" min="1" class="form-control" placeholder="Max points" />
              </div>
              <div class="col-md-4">
                <input v-model="q.correct_answer" class="form-control" placeholder="Correct answer" />
              </div>
            </div>
            <div v-if="q.question_type === 'multiple_choice'" class="row g-2">
              <div class="col-md-6"><input v-model="q.option_a" class="form-control" placeholder="Option A" /></div>
              <div class="col-md-6"><input v-model="q.option_b" class="form-control" placeholder="Option B" /></div>
              <div class="col-md-6"><input v-model="q.option_c" class="form-control" placeholder="Option C" /></div>
              <div class="col-md-6"><input v-model="q.option_d" class="form-control" placeholder="Option D" /></div>
              <div class="col-md-6"><input v-model="q.option_e" class="form-control" placeholder="Option E" /></div>
            </div>
          </div>

          <div class="d-flex gap-2">
            <button class="btn btn-outline-primary" @click="addQuestion">Add Question</button>
            <button class="btn btn-primary" @click="saveQuiz">Save Quiz</button>
            <button class="btn btn-outline-secondary" @click="resetForm">New Quiz</button>
          </div>
          <div class="mt-2 text-success">{{ status }}</div>
        </div>
      </div>

      <div class="col-lg-4">
        <div v-if="me.role === 'admin'" class="card card-soft p-3 mb-3">
          <h2 class="h6">Privileged Users</h2>
          <div class="input-group mb-2">
            <input v-model="privilegedEmail" class="form-control" placeholder="teacher@example.edu" />
            <button class="btn btn-primary" @click="addPrivileged">Add</button>
          </div>
          <ul class="list-group">
            <li v-for="u in privileged" :key="u.id" class="list-group-item d-flex justify-content-between align-items-center">
              {{ u.email }}
              <button class="btn btn-sm btn-outline-danger" @click="deletePrivileged(u.id)">Delete</button>
            </li>
          </ul>
        </div>

        <div class="card card-soft p-3">
          <h2 class="h6">Quizzes</h2>
          <div v-for="q in quizzes" :key="q.id" class="border rounded p-2 mb-2 bg-white">
            <div class="small text-muted">{{ q.code }} | {{ q.status }}</div>
            <div class="fw-bold">{{ q.title }}</div>
            <div class="d-flex flex-wrap gap-1 mt-2">
              <button class="btn btn-sm btn-outline-dark" @click="pickQuiz(q)">Watch</button>
              <button class="btn btn-sm btn-outline-primary" @click="editQuiz(q.code)">Edit</button>
              <button class="btn btn-sm btn-success" @click="startQuiz(q.id)">Start</button>
              <button class="btn btn-sm btn-warning" @click="stopQuiz(q.id)">Stop</button>
              <button class="btn btn-sm btn-secondary" @click="resetQuiz(q.id)">Reset</button>
              <button class="btn btn-sm btn-danger" @click="removeQuiz(q.id)">Delete</button>
              <button class="btn btn-sm btn-outline-info" @click="router.push(`/questions/${q.code}`)">Question Screen</button>
              <button class="btn btn-sm btn-outline-success" @click="router.push('/ranking')">Global Ranking</button>
            </div>
          </div>
        </div>

        <div v-if="wsStats" class="card card-soft p-3 mt-3">
          <h2 class="h6">Live Stats</h2>
          <div>Phase: {{ wsStats.phase }}</div>
          <div>Remaining: {{ wsStats.remaining_seconds }}s</div>
          <div>Participants: {{ wsStats.stats.participants }}</div>
          <div>Correct answers: {{ wsStats.stats.correct_answers }}</div>
          <div>Avg correct time: {{ wsStats.stats.avg_correct_seconds ?? '-' }}s</div>
        </div>
      </div>
    </div>
  </div>
</template>
