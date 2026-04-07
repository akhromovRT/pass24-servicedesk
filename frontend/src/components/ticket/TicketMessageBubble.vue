<script setup lang="ts">
import type { TicketComment, Attachment } from '../../types'
import TicketInlineAttachments from './TicketInlineAttachments.vue'

const props = defineProps<{
  comment: TicketComment
  attachments: Attachment[]
  isOwnMessage: boolean
  isStaff: boolean
}>()

const emit = defineEmits<{
  previewAttachment: [attachment: Attachment]
}>()

function formatTime(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function bubbleClass(): string {
  if (props.comment.is_internal) return 'bubble bubble--internal'
  if (props.isOwnMessage) return 'bubble bubble--own'
  if (props.isStaff) return 'bubble bubble--agent'
  return 'bubble bubble--client'
}
</script>

<template>
  <div
    class="message-row"
    :class="{ 'message-row--end': isOwnMessage }"
  >
    <div :class="bubbleClass()">
      <div class="bubble-header">
        <span class="author-name">{{ comment.author_name }}</span>
        <span class="message-time" :title="comment.created_at">
          {{ formatDate(comment.created_at) }}, {{ formatTime(comment.created_at) }}
        </span>
      </div>

      <div v-if="comment.is_internal" class="internal-badge">
        <i class="pi pi-lock" />
        <span>Внутренний</span>
      </div>

      <div class="bubble-body">{{ comment.text }}</div>

      <TicketInlineAttachments
        v-if="attachments.length > 0"
        :attachments="attachments"
        @preview="(att) => emit('previewAttachment', att)"
      />
    </div>
  </div>
</template>

<style scoped>
.message-row {
  display: flex;
  justify-content: flex-start;
}

.message-row--end {
  justify-content: flex-end;
}

.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 10px;
  position: relative;
}

/* Own message (agent's own) */
.bubble--own {
  background: #dbeafe;
  border-left: 3px solid #3b82f6;
}

/* Other agent messages */
.bubble--agent {
  background: #f0fdf4;
  border-left: 3px solid #10b981;
}

/* Client messages */
.bubble--client {
  background: #f8fafc;
  border-left: 3px solid #e2e8f0;
}

/* Internal comments */
.bubble--internal {
  background: #fef9c3;
  border-left: 3px solid #f59e0b;
}

.bubble-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 4px;
}

.author-name {
  font-size: 13px;
  font-weight: 600;
  color: #1e293b;
}

.message-time {
  font-size: 11px;
  color: #94a3b8;
}

.internal-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #92400e;
  background: #fde68a;
  border-radius: 4px;
  padding: 1px 6px;
  margin-bottom: 4px;
}

.internal-badge .pi {
  font-size: 10px;
}

.bubble-body {
  font-size: 14px;
  color: #334155;
  white-space: pre-wrap;
  line-height: 1.5;
  word-break: break-word;
}
</style>
