<script setup lang="ts">
import { computed } from 'vue'
import type { Attachment } from '../../types'

const props = defineProps<{
  attachments: Attachment[]
}>()

const emit = defineEmits<{
  preview: [attachment: Attachment]
}>()

function isImage(attachment: Attachment): boolean {
  return attachment.content_type.startsWith('image/')
}

function isPdf(attachment: Attachment): boolean {
  return attachment.content_type === 'application/pdf'
}

function fileIcon(attachment: Attachment): string {
  if (isPdf(attachment)) return 'pi pi-file-pdf'
  return 'pi pi-file'
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`
}

function thumbnailUrl(attachment: Attachment): string {
  return `/api/tickets/${attachment.ticket_id}/attachments/${attachment.id}`
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// Build object URLs for image thumbnails with auth
import { ref, onMounted, onBeforeUnmount } from 'vue'

const imageUrls = ref<Record<string, string>>({})

const imageAttachments = computed(() =>
  props.attachments.filter(isImage),
)

const fileAttachments = computed(() =>
  props.attachments.filter((a) => !isImage(a)),
)

async function loadImageThumbnail(attachment: Attachment) {
  try {
    const response = await fetch(thumbnailUrl(attachment), {
      headers: authHeaders(),
    })
    if (response.ok) {
      const blob = await response.blob()
      imageUrls.value[attachment.id] = URL.createObjectURL(blob)
    }
  } catch {
    // silent — thumbnail just won't show
  }
}

onMounted(() => {
  imageAttachments.value.forEach(loadImageThumbnail)
})

onBeforeUnmount(() => {
  Object.values(imageUrls.value).forEach(URL.revokeObjectURL)
})
</script>

<template>
  <div class="inline-attachments">
    <div
      v-for="att in imageAttachments"
      :key="att.id"
      class="attachment-thumbnail"
      @click="emit('preview', att)"
    >
      <img
        v-if="imageUrls[att.id]"
        :src="imageUrls[att.id]"
        :alt="att.filename"
        class="thumbnail-img"
      />
      <div v-else class="thumbnail-placeholder">
        <i class="pi pi-image" />
      </div>
    </div>

    <div
      v-for="att in fileAttachments"
      :key="att.id"
      class="attachment-chip"
      @click="emit('preview', att)"
    >
      <i :class="fileIcon(att)" class="chip-icon" />
      <span class="chip-name">{{ att.filename }}</span>
      <span class="chip-size">{{ formatFileSize(att.size) }}</span>
    </div>
  </div>
</template>

<style scoped>
.inline-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 8px;
}

.attachment-thumbnail {
  width: 64px;
  height: 64px;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  transition: border-color 0.15s;
}

.attachment-thumbnail:hover {
  border-color: #3b82f6;
}

.thumbnail-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumbnail-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  color: #94a3b8;
  font-size: 20px;
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 6px;
  background: #f1f5f9;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  transition: background 0.15s;
  max-width: 220px;
}

.attachment-chip:hover {
  background: #e2e8f0;
}

.chip-icon {
  font-size: 14px;
  color: #64748b;
  flex-shrink: 0;
}

.chip-name {
  font-size: 12px;
  color: #334155;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.chip-size {
  font-size: 11px;
  color: #94a3b8;
  white-space: nowrap;
  flex-shrink: 0;
}
</style>
