import { ref, computed } from 'vue'
import { useToast } from 'primevue/usetoast'
import type { Attachment } from '../types'

export function useTicketPreview() {
  const toast = useToast()
  const previewVisible = ref(false)
  const previewUrl = ref('')
  const previewFile = ref<Attachment | null>(null)
  const previewLoading = ref(false)

  const isImage = computed(() => previewFile.value?.content_type.startsWith('image/') ?? false)
  const isPdf = computed(() => previewFile.value?.content_type === 'application/pdf')
  const isText = computed(() => previewFile.value?.content_type.startsWith('text/') ?? false)

  async function openPreview(att: Attachment) {
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = ''
    }
    previewFile.value = att
    previewVisible.value = true
    previewLoading.value = true
    try {
      const token = localStorage.getItem('access_token')
      const resp = await fetch(`/tickets/${att.ticket_id}/attachments/${att.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const blob = await resp.blob()
      previewUrl.value = URL.createObjectURL(blob)
    } catch (e: any) {
      toast.add({ severity: 'error', summary: 'Ошибка', detail: e.message, life: 4000 })
      previewVisible.value = false
    } finally {
      previewLoading.value = false
    }
  }

  function closePreview() {
    previewVisible.value = false
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value)
      previewUrl.value = ''
    }
    previewFile.value = null
  }

  function downloadAttachment() {
    if (!previewUrl.value || !previewFile.value) return
    const a = document.createElement('a')
    a.href = previewUrl.value
    a.download = previewFile.value.filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  return {
    previewVisible,
    previewUrl,
    previewFile,
    previewLoading,
    isImage,
    isPdf,
    isText,
    openPreview,
    closePreview,
    downloadAttachment,
  }
}
