import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, setToken, clearToken, isAuthenticated } from '../api/client'
import type { User, Token } from '../types'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => !!user.value)

  async function fetchUser() {
    user.value = await api.get<User>('/auth/me')
  }

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const token = await api.post<Token>('/auth/login', { email, password })
      setToken(token.access_token)
      await fetchUser()
    } finally {
      loading.value = false
    }
  }

  async function register(
    email: string,
    password: string,
    full_name: string,
    role?: string,
  ) {
    loading.value = true
    try {
      await api.post('/auth/register', { email, password, full_name, role })
      const token = await api.post<Token>('/auth/login', { email, password })
      setToken(token.access_token)
      await fetchUser()
    } finally {
      loading.value = false
    }
  }

  function logout() {
    clearToken()
    user.value = null
  }

  async function init() {
    if (isAuthenticated()) {
      try {
        await fetchUser()
      } catch {
        clearToken()
        user.value = null
      }
    }
  }

  return { user, loading, isLoggedIn, login, register, logout, fetchUser, init }
})
