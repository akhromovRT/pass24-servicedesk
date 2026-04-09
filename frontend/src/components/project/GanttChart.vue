<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
} from 'echarts/components'
import VChart from 'vue-echarts'
import type { ProjectPhase } from '../../types'

use([CanvasRenderer, BarChart, TitleComponent, TooltipComponent, GridComponent, DataZoomComponent])

const props = defineProps<{
  phases: ProjectPhase[]
  plannedStart: string | null
  plannedEnd: string | null
}>()

const statusColors: Record<string, string> = {
  pending: '#cbd5e1',
  in_progress: '#3b82f6',
  completed: '#10b981',
  blocked: '#ef4444',
  skipped: '#94a3b8',
}

const statusLabels: Record<string, string> = {
  pending: 'Ожидает',
  in_progress: 'В работе',
  completed: 'Завершён',
  blocked: 'Заблокирован',
  skipped: 'Пропущен',
}

function toTimestamp(dateStr: string | null): number | null {
  if (!dateStr) return null
  return new Date(dateStr).getTime()
}

const chartOption = computed(() => {
  const sorted = [...props.phases].sort((a, b) => a.order_num - b.order_num)
  const categories = sorted.map(p => p.name)

  // Определяем диапазон дат
  const now = Date.now()
  let minDate = now
  let maxDate = now

  if (props.plannedStart) minDate = Math.min(minDate, new Date(props.plannedStart).getTime())
  if (props.plannedEnd) maxDate = Math.max(maxDate, new Date(props.plannedEnd).getTime())

  const barData: any[] = []

  sorted.forEach((phase, idx) => {
    const start = toTimestamp(phase.planned_start_date) || toTimestamp(phase.actual_start_date) || now
    const durationMs = (phase.planned_duration_days || 14) * 24 * 3600 * 1000
    const end = toTimestamp(phase.planned_end_date) || toTimestamp(phase.actual_end_date) || (start + durationMs)

    minDate = Math.min(minDate, start)
    maxDate = Math.max(maxDate, end)

    barData.push({
      name: phase.name,
      value: [idx, start, end, phase.status, phase.progress_pct],
      itemStyle: {
        color: statusColors[phase.status] || '#94a3b8',
        borderRadius: 4,
      },
    })
  })

  // Добавляем padding
  const padding = 7 * 24 * 3600 * 1000 // 1 неделя
  minDate -= padding
  maxDate += padding

  return {
    tooltip: {
      formatter: (params: any) => {
        const [, start, end, status, progress] = params.value
        const startStr = new Date(start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        const endStr = new Date(end).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
        return `<b>${params.name}</b><br/>
                ${startStr} — ${endStr}<br/>
                Статус: ${statusLabels[status] || status}<br/>
                Прогресс: ${progress}%`
      },
    },
    grid: {
      left: 200,
      right: 40,
      top: 20,
      bottom: 60,
    },
    xAxis: {
      type: 'time',
      min: minDate,
      max: maxDate,
      axisLabel: {
        formatter: (val: number) => new Date(val).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }),
      },
    },
    yAxis: {
      type: 'category',
      data: categories,
      inverse: true,
      axisLabel: {
        width: 180,
        overflow: 'truncate',
        fontSize: 12,
      },
    },
    dataZoom: [
      { type: 'slider', xAxisIndex: 0, bottom: 10, height: 20 },
    ],
    series: [{
      type: 'bar',
      encode: { x: [1, 2], y: 0 },
      data: barData,
      barMaxWidth: 18,
      renderItem: (_params: any, api: any) => {
        const categoryIndex = api.value(0)
        const start = api.coord([api.value(1), categoryIndex])
        const end = api.coord([api.value(2), categoryIndex])
        const height = 16

        return {
          type: 'rect',
          shape: {
            x: start[0],
            y: start[1] - height / 2,
            width: Math.max(end[0] - start[0], 4),
            height,
            r: 4,
          },
          style: api.style(),
        }
      },
    }],
  }
})
</script>

<template>
  <div class="gantt-container">
    <VChart :option="chartOption" style="height: 400px" autoresize />
  </div>
</template>

<style scoped>
.gantt-container {
  background: #fff;
  border-radius: 8px;
  padding: 16px;
}
</style>
