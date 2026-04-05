<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import Menubar from 'primevue/menubar'
import Button from 'primevue/button'
import Toast from 'primevue/toast'
import { useAuthStore } from './stores/auth'
import AiChat from './components/AiChat.vue'
import NotificationBell from './components/NotificationBell.vue'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const isStaff = computed(() =>
  auth.user?.role === 'support_agent' || auth.user?.role === 'admin'
)

const menuItems = computed(() => {
  const items = []

  // «Мои заявки» — первый пункт для авторизованных (ведёт на главную /)
  if (auth.isLoggedIn) {
    items.push({
      label: 'Мои заявки',
      icon: 'pi pi-ticket',
      command: () => router.push('/'),
      class: (route.path === '/' || (route.path.startsWith('/tickets') && route.path !== '/tickets/create')) ? 'p-menuitem-active' : '',
    })
  }

  items.push({
    label: 'Инструкции',
    icon: 'pi pi-map',
    command: () => router.push('/instructions'),
    class: (route.path.startsWith('/instructions') || (!auth.isLoggedIn && route.path === '/')) ? 'p-menuitem-active' : '',
  })

  items.push({
    label: 'База знаний',
    icon: 'pi pi-book',
    command: () => router.push('/knowledge'),
    class: route.path.startsWith('/knowledge') ? 'p-menuitem-active' : '',
  })

  if (isStaff.value) {
    items.push({
      label: 'Мой дашборд',
      icon: 'pi pi-th-large',
      command: () => router.push('/dashboard'),
      class: route.path === '/dashboard' ? 'p-menuitem-active' : '',
    })
    items.push({
      label: 'Аналитика',
      icon: 'pi pi-chart-bar',
      command: () => router.push('/analytics'),
      class: route.path === '/analytics' ? 'p-menuitem-active' : '',
    })
    items.push({
      label: 'Настройки',
      icon: 'pi pi-cog',
      command: () => router.push('/settings'),
      class: route.path === '/settings' ? 'p-menuitem-active' : '',
    })
  }

  return items
})

function logout() {
  auth.logout()
  router.push('/')
}
</script>

<template>
  <Toast />
  <div class="layout">
    <Menubar :model="menuItems" class="layout-header">
      <template #start>
        <span class="layout-brand" @click="router.push('/')">
          <span class="brand-icon">P24</span>
          <span class="brand-text">Service Desk</span>
        </span>
      </template>
      <template #end>
        <div v-if="auth.isLoggedIn" class="layout-user">
          <NotificationBell v-if="isStaff" />
          <span class="user-name">{{ auth.user?.full_name }}</span>
          <Button
            icon="pi pi-sign-out"
            severity="secondary"
            text
            rounded
            size="small"
            @click="logout"
          />
        </div>
        <Button
          v-else
          label="Войти"
          icon="pi pi-sign-in"
          severity="secondary"
          outlined
          size="small"
          @click="router.push('/login')"
        />
      </template>
    </Menubar>

    <main class="layout-main">
      <router-view />
    </main>

    <!-- AI-помощник доступен всегда -->
    <AiChat />
  </div>
</template>

<style>
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Inter', system-ui, sans-serif;
  background: #f8fafc;
  color: #1e293b;
}

.layout-header {
  border-radius: 0 !important;
  border-left: none !important;
  border-right: none !important;
  border-top: none !important;
}

.layout-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  margin-right: 16px;
}

.brand-icon {
  background: linear-gradient(135deg, #ef4444, #991b1b);
  color: white;
  font-weight: 700;
  font-size: 13px;
  padding: 4px 8px;
  border-radius: 6px;
}

.brand-text {
  font-weight: 600;
  font-size: 15px;
  color: #1e293b;
}

.layout-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-size: 14px;
  color: #64748b;
}

.layout-main {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 20px;
}
</style>
