<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const error = ref('')
const submitted = ref(false)

const showStaffLogin = ref(false)
const staffEmail = ref('')
const staffPassword = ref('')
const staffError = ref('')

const emailInvalid = () => submitted.value && !email.value.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)
const passwordInvalid = () => submitted.value && !password.value

async function onSubmit() {
  submitted.value = true
  error.value = ''

  if (emailInvalid() || passwordInvalid()) return

  try {
    await auth.login(email.value, password.value)
    const redirect = route.query.redirect as string
    router.push(redirect || '/')
  } catch (e: any) {
    error.value = e.message || 'Ошибка входа'
  }
}

async function onStaffSubmit() {
  staffError.value = ''
  if (!staffEmail.value || !staffPassword.value) {
    staffError.value = 'Заполните все поля'
    return
  }
  try {
    await auth.login(staffEmail.value, staffPassword.value)
    const redirect = route.query.redirect as string
    router.push(redirect || '/')
  } catch (e: any) {
    staffError.value = e.message || 'Ошибка входа'
  }
}
</script>

<template>
  <div class="auth-page">
    <Card class="auth-card">
      <template #title>
        <div class="auth-title">
          <span class="auth-brand">P24</span>
          <span>Вход в Service Desk</span>
        </div>
      </template>
      <template #content>
        <Message v-if="error" severity="error" :closable="false" class="auth-message">
          {{ error }}
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

          <div class="field">
            <label for="password">Пароль</label>
            <Password
              id="password"
              v-model="password"
              :feedback="false"
              toggle-mask
              :invalid="passwordInvalid()"
              fluid
            />
            <small v-if="passwordInvalid()" class="field-error">Введите пароль</small>
          </div>

          <Button
            type="submit"
            label="Войти"
            icon="pi pi-sign-in"
            :loading="auth.loading"
            fluid
          />
        </form>
      </template>
      <template #footer>
        <div class="auth-footer">
          Нет аккаунта?
          <router-link to="/register">Зарегистрироваться</router-link>
        </div>
      </template>
    </Card>

    <div class="staff-login">
      <Button
        label="Вход для агентов техподдержки"
        icon="pi pi-headphones"
        severity="secondary"
        text
        size="small"
        @click="showStaffLogin = !showStaffLogin"
      />
      <Card v-if="showStaffLogin" class="auth-card staff-card">
        <template #content>
          <Message v-if="staffError" severity="error" :closable="false" class="auth-message">
            {{ staffError }}
          </Message>
          <form class="auth-form" @submit.prevent="onStaffSubmit">
            <div class="field">
              <label for="staff-email">Email сотрудника</label>
              <InputText
                id="staff-email"
                v-model="staffEmail"
                type="email"
                placeholder="agent@pass24online.ru"
                fluid
              />
            </div>
            <div class="field">
              <label for="staff-password">Пароль</label>
              <Password
                id="staff-password"
                v-model="staffPassword"
                :feedback="false"
                toggle-mask
                fluid
              />
            </div>
            <Button
              type="submit"
              label="Войти как сотрудник"
              icon="pi pi-shield"
              severity="warn"
              :loading="auth.loading"
              fluid
            />
          </form>
        </template>
      </Card>
    </div>
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

.staff-login {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  width: 100%;
  max-width: 420px;
}

.staff-card {
  border: 1px dashed #e2e8f0;
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
