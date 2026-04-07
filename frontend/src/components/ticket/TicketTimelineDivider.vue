<script setup lang="ts">
defineProps<{
  description: string
  timestamp: string
}>()
</script>

<template>
  <div class="timeline-divider" :title="timestamp">
    <span class="timeline-line" />
    <span class="timeline-text">{{ description }}</span>
    <span class="timeline-line" />
  </div>
</template>

<style scoped>
.timeline-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0;
  user-select: none;
}

.timeline-line {
  flex: 1;
  height: 1px;
  background: #e2e8f0;
}

.timeline-text {
  color: #94a3b8;
  font-size: 12px;
  white-space: nowrap;
}
</style>
