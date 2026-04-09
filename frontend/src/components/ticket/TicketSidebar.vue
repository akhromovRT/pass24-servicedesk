<script setup lang="ts">
import { computed } from 'vue'
import Panel from 'primevue/panel'
import type { Ticket, TicketStatus } from '../../types'
import TicketStatusDropdown from './TicketStatusDropdown.vue'
import TicketSlaProgress from './TicketSlaProgress.vue'
import TicketAssignment from './TicketAssignment.vue'
import TicketContactInfo from './TicketContactInfo.vue'
import TicketObjectInfo from './TicketObjectInfo.vue'
import TicketClassification from './TicketClassification.vue'
import TicketTechnicalInfo from './TicketTechnicalInfo.vue'
import TicketMacros from './TicketMacros.vue'
import TicketEventsLog from './TicketEventsLog.vue'

const props = defineProps<{
  ticket: Ticket
  isStaff: boolean
}>()

const emit = defineEmits<{
  statusChanged: [newStatus: TicketStatus]
  assigned: [agentId: string | null]
  macroApplied: [macroId: string]
  objectUpdated: []
}>()

const hasTechnicalData = computed(() => {
  return !!(props.ticket.device_type || props.ticket.app_version || props.ticket.error_message)
})
</script>

<template>
  <aside class="ticket-sidebar">
    <!-- Status + SLA: always visible, not collapsible -->
    <div class="sidebar-section sidebar-section--fixed">
      <TicketStatusDropdown
        v-if="isStaff"
        :currentStatus="ticket.status"
        @changeStatus="emit('statusChanged', $event)"
      />
      <TicketSlaProgress v-if="isStaff" :ticket="ticket" />
    </div>

    <!-- Assignment: staff only -->
    <Panel v-if="isStaff" header="Назначение" toggleable>
      <TicketAssignment
        :assigneeId="ticket.assignee_id"
        :ticketId="ticket.id"
        @assigned="emit('assigned', $event)"
      />
    </Panel>

    <!-- Contact info -->
    <Panel header="Контактная информация" toggleable>
      <TicketContactInfo
        :contactName="ticket.contact_name"
        :contactEmail="ticket.contact_email"
        :contactPhone="ticket.contact_phone"
        :company="ticket.company"
      />
    </Panel>

    <!-- Object info -->
    <Panel header="Объект" toggleable>
      <TicketObjectInfo
        :objectName="ticket.object_name"
        :objectAddress="ticket.object_address"
        :accessPoint="ticket.access_point"
        :customerId="ticket.customer_id"
        :ticketId="ticket.id"
        :isStaff="isStaff"
        @updated="emit('objectUpdated')"
      />
    </Panel>

    <!-- Classification: staff only -->
    <Panel v-if="isStaff" header="Классификация" toggleable>
      <TicketClassification
        :product="ticket.product"
        :ticketType="ticket.ticket_type"
        :source="ticket.source"
      />
    </Panel>

    <!-- Technical info: staff only, only if data exists -->
    <Panel v-if="isStaff && hasTechnicalData" header="Техническая информация" toggleable>
      <TicketTechnicalInfo
        :deviceType="ticket.device_type"
        :appVersion="ticket.app_version"
        :errorMessage="ticket.error_message"
      />
    </Panel>

    <!-- Macros: staff only -->
    <Panel v-if="isStaff" header="Макросы" toggleable>
      <TicketMacros
        :ticketId="ticket.id"
        @macroApplied="emit('macroApplied', $event)"
      />
    </Panel>

    <!-- Events log: staff only, default collapsed -->
    <TicketEventsLog v-if="isStaff" :events="ticket.events" />
  </aside>
</template>

<style scoped>
.ticket-sidebar {
  width: 380px;
  min-width: 380px;
  background: #fafbfc;
  border-left: 1px solid #e2e8f0;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-section--fixed {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-bottom: 4px;
}
</style>
