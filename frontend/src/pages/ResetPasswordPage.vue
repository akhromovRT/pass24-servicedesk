<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Card from 'primevue/card'
import Password from 'primevue/password'
import Button from 'primevue/button'
import Message from 'primevue/message'
import { api } from '../api/client'

const router = useRouter()
const route = useRoute()

const token = computed(() => (route.query.token as string) || '')
const newPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const success = ref(false)
const loading = ref(false)
const submitted = ref(false)

const passwordInvalid = () => submitted.value && newPassword.value.length < 6
const confirmInvalid = () => submitted.value && newPassword.value !== confirmPassword.value
const noToken = computed(() => !token.value)

async function onSubmit() {
  submitted.value = true
  error.value = ''

  if (passwordInvalid() || confirmInvalid()) return

  loading.value = true
  try {
    await api.post('/auth/reset-password', {
      token: token.value,
      new_password: newPassword.value,
    })
    success.value = true
    setTimeout(() => router.push('/login'), 3000)
  } catch (e: any) {
    error.value = e.message || 'Ошибка при сбросе пароля'
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
          <span>Новый пароль</span>
        </div>
      </template>
      <template #content>
        <!-- Нет токена -->
        <div v-if="noToken" class="error-state">
          <i class="pi pi-link-slash" style="font-size: 2rem; color: #dc2626; margin-bottom: 1rem;"></i>
          <p class="error-title">Недействительная ссылка</p>
          <p class="error-text">
            Ссылка для сброса пароля повреждена или отсутствует.
            <router-link to="/forgot-password">Запросите новую ссылку</router-link>.
          </p>
        </div>

        <!-- Успех -->
        <div v-else-if="success" class="success-state">
          <div class="success-icon">
            <i class="pi pi-check-circle" style="font-size: 2rem; color: #059669;"></i>
          </div>
          <p class="success-title">Пароль изменён</p>
          <p class="success-text">
            Теперь вы можете войти с новым паролем. Перенаправляем на страницу входа...
          </p>
          <Button
            label="Войти сейчас"
            icon="pi pi-sign-in"
            @click="router.push('/login')"
            fluid
          />
        </div>

        <!-- Форма -->
        <template v-else>
          <p class="form-hint">
            Придумайте новый пароль для вашей учётной записи.
          </p>

          <Message v-if="error" severity="error" :closable="false" class="auth-message">
            {{ error }}
            <template v-if="error.includes('истёк') || error.includes('Недействительная')">
              <br><router-link to="/forgot-password" style="color: inherit; font-weight: 600;">Запросить новую ссылку</router-link>
            </template>
          </Message>

          <form class="auth-form" @submit.prevent="onSubmit">
            <div class="field">
              <label for="new-password">Новый пароль</label>
              <Password
                id="new-password"
                v-model="newPassword"
                :feedback="false"
                toggle-mask
                :invalid="passwordInvalid()"
                fluid
              />
              <small v-if="passwordInvalid()" class="field-error">Минимум 6 символов</small>
            </div>

            <div class="field">
              <label for="confirm-password">Подтвердите пароль</label>
              <Password
                id="confirm-password"
                v-model="confirmPassword"
                :feedback="false"
                toggle-mask
                :invalid="confirmInvalid()"
                fluid
              />
              <small v-if="confirmInvalid()" class="field-error">Пароли не совпадают</small>
            </div>

            <Button
              type="submit"
              label="Сохранить пароль"
              icon="pi pi-check"
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

.error-state {
  text-align: center;
  padding: 1rem 0;
}

.error-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 0.5rem;
}

.error-text {
  color: #475569;
  font-size: 0.875rem;
  line-height: 1.5;
  margin: 0;
}

.error-text a {
  color: var(--p-primary-color);
  text-decoration: none;
  font-weight: 500;
}

.error-text a:hover {
  text-decoration: underline;
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
