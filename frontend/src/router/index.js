import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../pages/HomePage.vue'
import AdminPage from '../pages/AdminPage.vue'
import QuizPlayerPage from '../pages/QuizPlayerPage.vue'
import QuestionScreenPage from '../pages/QuestionScreenPage.vue'
import GlobalRankingPage from '../pages/GlobalRankingPage.vue'
import { getToken, getUser } from '../services/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomePage },
    { path: '/admin', component: AdminPage, meta: { requiresAuth: true, privileged: true } },
    { path: '/quiz/:code', component: QuizPlayerPage, meta: { requiresAuth: true } },
    { path: '/questions/:code', component: QuestionScreenPage, meta: { requiresAuth: true, privileged: true } },
    { path: '/ranking', component: GlobalRankingPage, meta: { requiresAuth: true } }
  ]
})

router.beforeEach((to) => {
  const token = getToken()
  const user = getUser()

  if (to.meta.requiresAuth && !token) {
    return '/'
  }
  if (to.meta.privileged && (!user || !['admin', 'privileged'].includes(user.role))) {
    return '/'
  }
  return true
})

export default router
