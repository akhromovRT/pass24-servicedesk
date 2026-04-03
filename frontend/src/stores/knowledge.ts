import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Article, ArticleCreate, PaginatedResponse } from '../types'

export const useKnowledgeStore = defineStore('knowledge', () => {
  const articles = ref<Article[]>([])
  const currentArticle = ref<Article | null>(null)
  const total = ref(0)
  const page = ref(1)
  const loading = ref(false)
  const searchQuery = ref('')

  async function fetchArticles(p = 1, category?: string, type?: string) {
    loading.value = true
    try {
      let path = `/knowledge/?page=${p}&per_page=20`
      if (category) path += `&category=${category}`
      if (type) path += `&type=${type}`
      const data = await api.get<PaginatedResponse<Article>>(path)
      articles.value = data.items
      total.value = data.total
      page.value = data.page
    } finally {
      loading.value = false
    }
  }

  async function searchArticles(query: string, p = 1, type?: string) {
    loading.value = true
    try {
      let path = `/knowledge/search?query=${encodeURIComponent(query)}&page=${p}`
      if (type) path += `&type=${type}`
      const data = await api.get<PaginatedResponse<Article>>(path)
      articles.value = data.items
      total.value = data.total
      page.value = data.page
      searchQuery.value = query
    } finally {
      loading.value = false
    }
  }

  async function fetchArticle(slug: string) {
    loading.value = true
    try {
      currentArticle.value = await api.get<Article>(`/knowledge/${slug}`)
    } finally {
      loading.value = false
    }
  }

  async function createArticle(data: ArticleCreate) {
    const article = await api.post<Article>('/knowledge/', data)
    return article
  }

  async function deleteArticle(id: string) {
    await api.delete(`/knowledge/${id}`)
    articles.value = articles.value.filter((a) => a.id !== id)
    total.value = Math.max(0, total.value - 1)
  }

  return {
    articles,
    currentArticle,
    total,
    page,
    loading,
    searchQuery,
    fetchArticles,
    searchArticles,
    fetchArticle,
    createArticle,
    deleteArticle,
  }
})
