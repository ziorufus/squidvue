<script setup>
import { onMounted, ref } from 'vue'

const emit = defineEmits(['credential'])
const target = ref(null)
const isRendered = ref(false)

function renderGoogleButton() {
  if (isRendered.value || !window.google?.accounts?.id || !target.value) return

  window.google.accounts.id.initialize({
    client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
    callback: (res) => emit('credential', res.credential)
  })

  window.google.accounts.id.renderButton(target.value, {
    theme: 'outline',
    size: 'large',
    shape: 'pill',
    text: 'continue_with'
  })

  isRendered.value = true
}

function waitForGoogleSDK() {
  if (window.google?.accounts?.id) {
    renderGoogleButton()
    return
  }

  const existingScript = document.querySelector('script[src="https://accounts.google.com/gsi/client"]')

  if (!existingScript) {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = renderGoogleButton
    document.head.appendChild(script)
    return
  }

  existingScript.addEventListener('load', renderGoogleButton, { once: true })

  let attempts = 0
  const interval = window.setInterval(() => {
    if (window.google?.accounts?.id) {
      window.clearInterval(interval)
      renderGoogleButton()
      return
    }
    attempts += 1
    if (attempts >= 50) window.clearInterval(interval)
  }, 100)
}

onMounted(() => {
  waitForGoogleSDK()
})
</script>

<template>
  <div ref="target"></div>
</template>
