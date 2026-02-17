const KEY = 'quiz_token'
const USER_KEY = 'quiz_user'

export function setSession(token, user) {
  localStorage.setItem(KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession() {
  localStorage.removeItem(KEY)
  localStorage.removeItem(USER_KEY)
}

export function getToken() {
  return localStorage.getItem(KEY)
}

export function getUser() {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}
