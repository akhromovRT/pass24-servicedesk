<script setup lang="ts">
import type { ProjectType } from '../types'

defineProps<{ type: ProjectType }>()

const typeLabels: Record<ProjectType, string> = {
  residential: 'ЖК',
  commercial: 'БЦ',
  cameras_only: 'Камеры',
  large_construction: 'Большая стройка',
}

const typeIcons: Record<ProjectType, string> = {
  residential: 'pi pi-home',
  commercial: 'pi pi-building',
  cameras_only: 'pi pi-camera',
  large_construction: 'pi pi-wrench',
}

const typeColors: Record<ProjectType, string> = {
  residential: '#3b82f6',
  commercial: '#8b5cf6',
  cameras_only: '#10b981',
  large_construction: '#f59e0b',
}
</script>

<template>
  <span class="project-type-badge" :style="{ color: typeColors[type] }">
    <i :class="typeIcons[type]" />
    <span>{{ typeLabels[type] }}</span>
  </span>
</template>

<style scoped>
.project-type-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 0.875rem;
  font-weight: 500;
}
.project-type-badge i {
  font-size: 0.875rem;
}
</style>
