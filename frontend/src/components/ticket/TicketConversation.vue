<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { Ticket, Attachment, TicketComment, TicketEvent } from '../../types'
import { parseUTC } from '../../utils/date'
import { useTicketConversation, type TimelineItem } from '../../composables/useTicketConversation'
import { useAuthStore } from '../../stores/auth'
import TicketTimelineDivider from './TicketTimelineDivider.vue'
import TicketMessageBubble from './TicketMessageBubble.vue'
import TicketInlineAttachments from './TicketInlineAttachments.vue'

const props = defineProps<{
  ticket: Ticket
  isStaff: boolean
}>()

const emit = defineEmits<{
  previewAttachment: [attachment: Attachment]
}>()

const auth = useAuthStore()

const ticketRef = computed(() => props.ticket)
const { timeline } = useTicketConversation(ticketRef)

const bottomSentinel = ref<HTMLElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    bottomSentinel.value?.scrollIntoView({ behavior: 'smooth' })
  })
}

// Auto-scroll when ticket data changes (new comments/events)
watch(
  () => props.ticket.comments.length + props.ticket.events.length,
  () => scrollToBottom(),
  { flush: 'post' },
)

// Scroll on mount
watch(
  () => props.ticket.id,
  () => scrollToBottom(),
  { immediate: true, flush: 'post' },
)

// Attachments without a comment_id belong to the ticket description
const descriptionAttachments = computed<Attachment[]>(() =>
  props.ticket.attachments.filter((a) => a.comment_id === null),
)

function attachmentsForComment(commentId: string): Attachment[] {
  return props.ticket.attachments.filter((a) => a.comment_id === commentId)
}

function isComment(item: TimelineItem): item is TimelineItem & { data: TicketComment } {
  return item.type === 'comment'
}

function isEvent(item: TimelineItem): item is TimelineItem & { data: TicketEvent } {
  return item.type === 'event'
}

function formatTimestamp(dateStr: string): string {
  return parseUTC(dateStr).toLocaleString('ru-RU', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div class="conversation">
    <!-- Original ticket description as first "message" -->
    <div class="message-row">
      <div class="bubble bubble--client">
        <div class="bubble-header">
          <span class="author-name">{{ ticket.contact_name || 'Автор' }}</span>
          <span class="message-time" :title="ticket.created_at">
            {{ formatTimestamp(ticket.created_at) }}
          </span>
        </div>
        <div class="bubble-title">{{ ticket.title }}</div>
        <div class="bubble-body">{{ ticket.description }}</div>
        <TicketInlineAttachments
          v-if="descriptionAttachments.length > 0"
          :attachments="descriptionAttachments"
          @preview="(att: Attachment) => emit('previewAttachment', att)"
        />
      </div>
    </div>

    <!-- Timeline items -->
    <template v-for="item in timeline" :key="item.data.id">
      <TicketTimelineDivider
        v-if="isEvent(item)"
        :description="(item.data as TicketEvent).description"
        :timestamp="formatTimestamp(item.data.created_at)"
      />

      <TicketMessageBubble
        v-else-if="isComment(item)"
        :comment="(item.data as TicketComment)"
        :attachments="attachmentsForComment((item.data as TicketComment).id)"
        :is-own-message="(item.data as TicketComment).author_id === auth.user?.id"
        :is-staff="isStaff"
        @preview-attachment="(att) => emit('previewAttachment', att)"
      />
    </template>

    <!-- Bottom sentinel for auto-scroll -->
    <div ref="bottomSentinel" class="bottom-sentinel" />
  </div>
</template>

<style scoped>
.conversation {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 400px;
  padding: 16px;
  overflow-y: auto;
}

.message-row {
  display: flex;
  justify-content: flex-start;
}

.bubble {
  max-width: 75%;
  padding: 10px 14px;
  border-radius: 10px;
}

.bubble--client {
  background: #f8fafc;
  border-left: 3px solid #e2e8f0;
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

.bubble-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
  margin-bottom: 4px;
}

.bubble-body {
  font-size: 14px;
  color: #334155;
  white-space: pre-wrap;
  line-height: 1.5;
  word-break: break-word;
}

.bottom-sentinel {
  height: 1px;
  flex-shrink: 0;
}
</style>
