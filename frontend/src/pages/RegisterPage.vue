<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import InputText from 'primevue/inputtext'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Message from 'primevue/message'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const fullName = ref('')
const role = ref('')
const error = ref('')
const submitted = ref(false)

const roleOptions = [
  { label: 'Житель', value: 'resident' },
  { label: 'Администратор УК', value: 'property_manager' },
  { label: 'Агент поддержки', value: 'support_agent' },
]

const emailInvalid = () => submitted.value && !email.value.match(/^[^\s@]+@[^\s@]+\.[^\s@]+$/)
const passwordInvalid = () => submitted.value && (password.value.length < 6)
const fullNameInvalid = () => submitted.value && !fullName.value.trim()
const roleInvalid = () => submitted.value && !role.value

async function onSubmit() {
  submitted.value = true
  error.value = ''

  if (emailInvalid() || passwordInvalid() || fullNameInvalid() || roleInvalid()) return

  try {
    await auth.register(email.value, password.value, fullName.value, role.value)
    router.push('/')
  } catch (e: any) {
    error.value = e.message || 'Ошибка регистрации'
  }
}
</script>

<template>
  <div class="auth-page">
    <Card class="auth-card">
      <template #title>
        <div class="auth-title">
          <span class="auth-brand">P24</span>
          <span>Регистрация</span>
        </div>
      </template>
      <template #content>
        <Message v-if="error" severity="error" :closable="false" class="auth-message">
          {{ error }}
        </Message>

        <form class="auth-form" @submit.prevent="onSubmit">
          <div class="field">
            <label for="fullName">Имя и фамилия</label>
            <InputText
              id="fullName"
              v-model="fullName"
              placeholder="Иван Иванов"
              :invalid="fullNameInvalid()"
              fluid
            />
            <small v-if="fullNameInvalid()" class="field-error">Введите имя и фамилию</small>
          </div>

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
            <small v-if="passwordInvalid()" class="field-error">Минимум 6 символов</small>
          </div>

          <div class="field">
            <label for="role">Роль</label>
            <Select
              id="role"
              v-model="role"
              :options="roleOptions"
              option-label="label"
              option-value="value"
              placeholder="Выберите роль"
              :invalid="roleInvalid()"
              fluid
            />
            <small v-if="roleInvalid()" class="field-error">Выберите роль</small>
          </div>

          <Button
            type="submit"
            label="Зарегистрироваться"
            icon="pi pi-user-plus"
            :loading="auth.loading"
            fluid
          />
        </form>
      </template>
      <template #footer>
        <div class="auth-footer">
          Уже есть аккаунт?
          <router-link to="/login">Войти</router-link>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.auth-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 80vh;
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
