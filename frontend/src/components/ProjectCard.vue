<script setup lang="ts">
import Card from 'primevue/card'
import ProgressBar from 'primevue/progressbar'
import ProjectStatusBadge from './ProjectStatusBadge.vue'
import ProjectTypeBadge from './ProjectTypeBadge.vue'
import type { ProjectListItem } from '../types'

defineProps<{ project: ProjectListItem }>()
defineEmits<{ click: [] }>()

function formatDate(d: string | null): string {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  })
}
</script>

<template>
  <Card class="project-card" @click="$emit('click')">
    <template #title>
      <div class="card-title">
        <span class="code">{{ project.code }}</span>
        <ProjectStatusBadge :status="project.status" />
      </div>
    </template>
    <template #subtitle>
      <div class="card-subtitle">
        <strong>{{ project.name }}</strong>
        <ProjectTypeBadge :type="project.project_type" />
      </div>
    </template>
    <template #content>
      <div class="card-meta">
        <div class="meta-row">
          <i class="pi pi-briefcase" />
          <span>{{ project.customer_company }}</span>
        </div>
        <div class="meta-row">
          <i class="pi pi-map-marker" />
          <span>{{ project.object_name }}</span>
        </div>
        <div class="meta-row" v-if="project.planned_end_date">
          <i class="pi pi-calendar" />
          <span>План: {{ formatDate(project.planned_end_date) }}</span>
        </div>
      </div>

      <div class="progress-section">
        <div class="progress-label">
          <span>Прогресс</span>
          <strong>{{ project.progress_pct }}%</strong>
        </div>
        <ProgressBar :value="project.progress_pct" :show-value="false" />
      </div>
    </template>
  </Card>
</template>

<style scoped>
.project-card {
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
  height: 100%;
}
.project-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}
.card-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.code {
  font-family: monospace;
  font-size: 0.75rem;
  font-weight: 600;
  color: #64748b;
}
.card-subtitle {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.card-subtitle strong {
  color: var(--p-text-color);
  font-size: 1rem;
}
.card-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}
.meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.875rem;
  color: #64748b;
}
.meta-row i {
  width: 16px;
  color: #94a3b8;
}
.progress-section {
  margin-top: 12px;
}
.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 0.8rem;
  color: #64748b;
  margin-bottom: 4px;
}
</style>
