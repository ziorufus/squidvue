import axios from 'axios'
import { clearSession, getToken, setSession } from './auth'

const baseURL = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

const api = axios.create({ baseURL })

let authCheckPromise = null

function forceLogoutAndRedirectHome() {
  clearSession()
  if (window.location.pathname !== '/') {
    window.location.assign('/')
  }
}

async function verifySession() {
  const token = getToken()
  if (!token) return false

  const response = await axios.get(`${baseURL}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
    validateStatus: () => true
  })

  if (response.status === 200) {
    setSession(token, response.data)
    return true
  }
  return false
}

api.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const status = error?.response?.status
    const originalRequest = error?.config || {}

    if (status !== 401 || originalRequest._skipAuthRecheck) {
      return Promise.reject(error)
    }

    if (!authCheckPromise) {
      authCheckPromise = verifySession().finally(() => {
        authCheckPromise = null
      })
    }

    const stillLogged = await authCheckPromise
    if (!stillLogged) {
      forceLogoutAndRedirectHome()
    }

    return Promise.reject(error)
  }
)

export default api
