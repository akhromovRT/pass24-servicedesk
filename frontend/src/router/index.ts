import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Публичные страницы (главный путь пользователя)
    {
      path: '/',
      name: 'home',
      component: () => import('../pages/InstructionsPage.vue'),
    },
    {
      path: '/instructions',
      name: 'instructions',
      component: () => import('../pages/InstructionsPage.vue'),
    },
    {
      path: '/instructions/:slug',
      name: 'guide',
      component: () => import('../pages/GuidePage.vue'),
    },
    {
      path: '/knowledge',
      name: 'knowledge',
      component: () => import('../pages/KnowledgePage.vue'),
    },
    {
      path: '/knowledge/:slug',
      name: 'article',
      component: () => import('../pages/ArticlePage.vue'),
    },
    // Авторизация
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../pages/RegisterPage.vue'),
      meta: { guest: true },
    },
    // Требуют авторизации
    {
      path: '/tickets',
      name: 'tickets',
      component: () => import('../pages/TicketsPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/tickets/create',
      name: 'ticket-create',
      component: () => import('../pages/CreateTicketPage.vue'),
      // Доступно без авторизации — гостевой тикет по email
    },
    {
      path: '/tickets/:id',
      name: 'ticket-detail',
      component: () => import('../pages/TicketDetailPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/analytics',
      name: 'analytics',
      component: () => import('../pages/AnalyticsPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../pages/SettingsPage.vue'),
      meta: { auth: true },
    },
  ],
})

router.beforeEach((to) => {
  if (to.meta.auth && !isAuthenticated()) {
    // Сохраняем куда хотели попасть
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guest && isAuthenticated()) {
    return { name: 'home' }
  }
})

export default router
