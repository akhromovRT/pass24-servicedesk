import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../api/client'

const router = createRouter({
  history: createWebHistory(),
  routes: [
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
    {
      path: '/',
      name: 'tickets',
      component: () => import('../pages/TicketsPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/tickets/create',
      name: 'ticket-create',
      component: () => import('../pages/CreateTicketPage.vue'),
      meta: { auth: true },
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
      path: '/instructions',
      name: 'instructions',
      component: () => import('../pages/InstructionsPage.vue'),
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
  ],
})

router.beforeEach((to) => {
  if (to.meta.auth && !isAuthenticated()) {
    return { name: 'login' }
  }
  if (to.meta.guest && isAuthenticated()) {
    return { name: 'tickets' }
  }
})

export default router
