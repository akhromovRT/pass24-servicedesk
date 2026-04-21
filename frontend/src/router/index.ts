import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../api/client'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Embed-виджет AI-чата для сторонних сайтов (iframe через chat-loader.js).
    // App.vue отключает navbar/floating AiChat на этом роуте.
    {
      path: '/chat-widget',
      name: 'chat-widget',
      component: () => import('../pages/ChatWidgetPage.vue'),
      meta: { public: true, embed: true },
    },
    // Главная: для авторизованных — заявки, для гостей — база знаний
    {
      path: '/',
      name: 'home',
      component: () => import('../pages/TicketsPage.vue'),
      beforeEnter: (_to) => {
        if (!isAuthenticated()) {
          return { name: 'knowledge' }
        }
      },
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
    // Обратная совместимость: старые ссылки /instructions → /knowledge
    {
      path: '/instructions',
      redirect: '/knowledge',
    },
    {
      path: '/instructions/:slug',
      redirect: (to) => `/knowledge/${to.params.slug}`,
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
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../pages/ForgotPasswordPage.vue'),
      meta: { guest: true },
    },
    {
      path: '/reset-password',
      name: 'reset-password',
      component: () => import('../pages/ResetPasswordPage.vue'),
      meta: { guest: true },
    },
    // Требуют авторизации
    {
      path: '/tickets',
      name: 'tickets',
      redirect: { name: 'home' },
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
      path: '/dashboard',
      name: 'dashboard',
      component: () => import('../pages/AgentDashboardPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/kb-analytics',
      name: 'kb-analytics',
      component: () => import('../pages/KbAnalyticsPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../pages/SettingsPage.vue'),
      meta: { auth: true },
    },
    // Implementation Projects
    {
      path: '/projects',
      name: 'projects',
      component: () => import('../pages/ProjectsListPage.vue'),
      meta: { auth: true },
    },
    {
      path: '/projects/analytics',
      name: 'project-analytics',
      component: () => import('../pages/ProjectAnalyticsPage.vue'),
      meta: { auth: true, roles: ['support_agent', 'admin'] },
    },
    {
      path: '/projects/create',
      name: 'project-create',
      component: () => import('../pages/ProjectCreatePage.vue'),
      meta: { auth: true, roles: ['admin'] },
    },
    {
      path: '/projects/:id',
      name: 'project-detail',
      component: () => import('../pages/ProjectDetailPage.vue'),
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
  // RBAC по meta.roles
  if (to.meta.roles && isAuthenticated()) {
    const auth = useAuthStore()
    const userRole = auth.user?.role
    const allowedRoles = to.meta.roles as string[]
    if (!userRole || !allowedRoles.includes(userRole)) {
      return { name: 'home' }
    }
  }
})

export default router
