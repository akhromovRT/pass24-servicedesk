<script setup lang="ts">
import { ref } from 'vue'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { api } from '../api/client'

const email = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)
const submitted = ref(false)

const emailInvalid = () => submitted.value && !email.value.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)

function maskEmail(e: string): string {
  const [local, domain] = e.split('@')
  if (local.length <= 2) return `${local[0]}***@${domain}`
  return `${local[0]}${local[1]}${'*'.repeat(Math.min(local.length - 2, 5))}@${domain}`
}

async function onSubmit() {
  submitted.value = true
  error.value = ''

  if (emailInvalid()) return

  loading.value = true
  try {
    await api.post('/auth/forgot-password', { email: email.value })
    success.value = true
  } catch (e: any) {
    error.value = e.message || 'Ошибка при отправке запроса'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <Card class="auth-card">
      <template #title>
        <div class="auth-title">
          <span class="auth-brand">P24</span>
          <span>Восстановление пароля</span>
        </div>
      </template>
      <template #content>
        <!-- Успешная отправка -->
        <div v-if="success" class="success-state">
          <div class="success-icon">
            <i class="pi pi-envelope" style="font-size: 2rem; color: #059669;"></i>
          </div>
          <p class="success-title">Письмо отправлено</p>
          <p class="success-text">
            Мы отправили ссылку для сброса пароля на
            <strong>{{ maskEmail(email) }}</strong>.
            Проверьте почту и перейдите по ссылке.
          </p>
          <p class="success-hint">
            Не получили письмо? Проверьте папку «Спам» или
            <a href="#" @click.prevent="success = false; error = ''">попробуйте снова</a>.
          </p>
        </div>

        <!-- Форма ввода email -->
        <template v-else>
          <p class="form-hint">
            Введите email, указанный при регистрации. Мы отправим вам ссылку для создания нового пароля.
          </p>

          <Message v-if="error" severity="error" :closable="false" class="auth-message">
            {{ error }}
            <template v-if="error.includes('не найден')">
              <br><router-link to="/register" style="color: inherit; font-weight: 600;">Зарегистрироваться</router-link>
            </template>
          </Message>

          <form class="auth-form" @submit.prevent="onSubmit">
            <div class="field">
              <label for="email">Email</label>
              <InputText
                id="email"
                v-model="email"
                type="email"
                placeholder="user@example.com"
                :invalid="emailInvalid()"
                fluid
              />
              <small v-if="emailInvalid()" class="field-error">Введите корректный email</small>
            </div>

            <Button
              type="submit"
              label="Отправить ссылку"
              icon="pi pi-send"
              :loading="loading"
              fluid
            />
          </form>
        </template>
      </template>
      <template #footer>
        <div class="auth-footer">
          <router-link to="/login">Вернуться ко входу</router-link>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
  gap: 16px;
}

.auth-card {
  width: 100%;
  max-width: 420px;
}

.auth-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 1.25rem;
}

.auth-brand {
  background: linear-gradient(135deg, #ef4444, #991b1b);
  color: white;
  font-weight: 700;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
}

.auth-message {
  margin-bottom: 1rem;
}

.form-hint {
  color: #64748b;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0 0 1.25rem;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.field label {
  font-weight: 500;
  font-size: 0.875rem;
}

.field-error {
  color: var(--p-red-500);
  font-size: 0.75rem;
}

.success-state {
  text-align: center;
  padding: 1rem 0;
}

.success-icon {
  margin-bottom: 1rem;
}

.success-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 0.5rem;
}

.success-text {
  color: #475569;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0 0 1rem;
}

.success-hint {
  color: #94a3b8;
  font-size: 0.8rem;
  margin: 0;
}

.success-hint a {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
}

.success-hint a:hover {
  text-decoration: underline;
}

.auth-footer {
  text-align: center;
  font-size: 0.875rem;
  color: #64748b;
}

.auth-footer a {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
}

.auth-footer a:hover {
  text-decoration: underline;
}
</style>
