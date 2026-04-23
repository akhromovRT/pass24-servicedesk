import { createApp } from 'vue'
import { createPinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Aura from '@primeuix/themes/aura'
import ToastService from 'primevue/toastservice'
import ConfirmationService from 'primevue/confirmationservice'
import 'primeicons/primeicons.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { clearToken } from './api/client'

const app = createApp(App)

const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: false,
    },
  },
})
app.use(ToastService)
app.use(ConfirmationService)

// Embed /chat-widget грузится в iframe на сторонних сайтах и всегда
// работает в guest-режиме. Если в localStorage (origin support.pass24pro.ru)
// остался устаревший JWT от прошлой прямой сессии, он даст 401 на /auth/me
// или /assistant/chat → api/client сделает window.location.href='/login'
// прямо внутри iframe. Поэтому для embed-роута пропускаем auth.init() и
// чистим токен заранее.
const isEmbed = window.location.pathname === '/chat-widget'
if (isEmbed) {
  clearToken()
} else {
  const auth = useAuthStore()
  auth.init()
}

app.mount('#app')
