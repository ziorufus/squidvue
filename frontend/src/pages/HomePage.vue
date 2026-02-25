<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import GoogleLoginButton from '../components/GoogleLoginButton.vue'
import api from '../services/api'
import { clearSession, getUser, setSession } from '../services/auth'

const router = useRouter()
const code = ref('')
const user = ref(getUser())
const error = ref('')

const isPrivileged = computed(() => user.value && ['admin', 'privileged'].includes(user.value.role))

async function onCredential(credential) {
  error.value = ''
  try {
    const login = await api.post('/api/auth/google', { credential })
    const me = await api.get('/api/auth/me', {
      headers: { Authorization: `Bearer ${login.data.access_token}` }
    })
    setSession(login.data.access_token, me.data)
    user.value = me.data
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Login failed'
  }
}

function logout() {
  clearSession()
  user.value = null
}

function joinQuiz() {
  if (!code.value.trim()) return
  router.push(`/quiz/${code.value.trim().toUpperCase()}`)
}
</script>

<template>
  <div class="container py-5">
    <div class="row justify-content-center">
      <div class="col-lg-7">
        <div class="card card-soft p-4">
          <h1 class="h3 mb-2">Lesson Quiz Platform</h1>
          <p class="text-muted">Login with Google, then join a quiz code shared by your teacher.</p>

          <div v-if="!user" class="mt-3">
            <GoogleLoginButton @credential="onCredential" />
            <div v-if="error" class="text-danger mt-2">{{ error }}</div>
          </div>

          <div v-else class="mt-3">
            <div class="mb-3">Signed in as <strong>{{ user.email }}</strong> ({{ user.role }})</div>
            <div class="d-flex gap-2">
              <input v-model="code" class="form-control" placeholder="Enter 5-char quiz code" maxlength="5" />
              <button class="btn btn-primary" @click="joinQuiz">Join</button>
            </div>
            <div class="mt-3 d-flex gap-2">
              <button v-if="isPrivileged" class="btn btn-outline-dark" @click="router.push('/admin')">Admin Panel</button>
              <button class="btn btn-outline-success" @click="router.push('/ranking')">Global Ranking</button>
              <button class="btn btn-outline-secondary" @click="logout">Logout</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
