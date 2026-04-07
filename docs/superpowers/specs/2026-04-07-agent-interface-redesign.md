# Agent Interface Redesign — Spec

## Context

Agent (support staff) feedback identified 6 major pain points in the current ticket management interface:
1. Each incoming email creates a new ticket instead of being threaded
2. Ticket detail page uses a "landing page" layout — single column with colored info blocks — instead of modern help desk UX
3. Attachments are in a separate section, not inline with conversation
4. Agent ticket list doesn't sort by newest first
5. Statuses stay "new" regardless of agent actions (auto-transition bug: goes to waiting_for_user instead of in_progress)
6. Missing manual statuses: "on hold" and "engineer visit"

The redesign transforms the agent ticket detail page from a single-column card layout into a 2-column chat-centric interface (like Zendesk/Freshdesk), adds 2 new statuses to the FSM, fixes auto-status logic, improves email threading reliability, and introduces inline attachments.

## Architecture

### Current State
- `TicketDetailPage.vue`: 2,180-line monolith with all ticket functionality
- `TicketsPage.vue`: 784 lines, ticket list with tabs and filters
- Backend FSM: 5 statuses (new, in_progress, waiting_for_user, resolved, closed)
- Email threading: subject tag `[PASS24-xxxxxxxx]` + Re: subject fallback
- Attachments: ticket-level only (no comment association)

### Target State
- `TicketDetailPage.vue`: ~200-line shell with 18 child components
- 4 composables for shared logic
- Backend FSM: 7 statuses (+on_hold, +engineer_visit)
- Email threading: subject tag + body tag + In-Reply-To headers + body-match
- Attachments: comment-level association with inline display

## Detailed Design

### 1. New Statuses — FSM Extension

Add to `TicketStatus` enum in `backend/tickets/models.py`:
```python
ON_HOLD = "on_hold"
ENGINEER_VISIT = "engineer_visit"
```

Updated transition table:
```python
allowed = {
    TicketStatus.NEW: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.IN_PROGRESS: {
        TicketStatus.WAITING_FOR_USER,
        TicketStatus.ON_HOLD,
        TicketStatus.ENGINEER_VISIT,
        TicketStatus.RESOLVED,
    },
    TicketStatus.WAITING_FOR_USER: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.ON_HOLD: {TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED},
    TicketStatus.ENGINEER_VISIT: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.WAITING_FOR_USER,
    },
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.IN_PROGRESS},
}
```

SLA pause logic update (in `transition()` method):
- Pause on entering: `WAITING_FOR_USER` or `ON_HOLD`
- Resume on leaving: `WAITING_FOR_USER` or `ON_HOLD`
- `ENGINEER_VISIT` does NOT pause SLA (work is happening, just offsite)

Status display:
| Status | Agent label | User label | Color | PrimeVue severity |
|--------|-----------|-----------|-------|------------------|
| on_hold | Отложена | Отложена | #6366f1 (indigo) | secondary |
| engineer_visit | Выезд инженера | Инженер выехал | #0ea5e9 (sky) | info |

Database migration: `ALTER TYPE ticketstatus ADD VALUE IF NOT EXISTS 'on_hold'` and same for `engineer_visit`. PostgreSQL enum ALTER cannot be in a transaction block.

### 2. Auto-Status on First Agent Response

Change in `backend/tickets/router.py`, `add_comment()` endpoint (lines 764-773):

**Before:**
```python
# Agent commented on NEW or IN_PROGRESS → WAITING_FOR_USER
if ticket.status in (TicketStatus.NEW, TicketStatus.IN_PROGRESS):
    event = ticket.transition(actor_id, TicketStatus.WAITING_FOR_USER)
```

**After:**
```python
# Agent commented on NEW → IN_PROGRESS (first response)
if ticket.status == TicketStatus.NEW:
    event = ticket.transition(actor_id, TicketStatus.IN_PROGRESS)
# Agent on IN_PROGRESS → no auto-change (agent controls manually)
```

Client reply logic stays: `WAITING_FOR_USER → IN_PROGRESS`.

### 3. Ticket List — Default Sort

In `backend/tickets/router.py`, `list_tickets()`:
- For staff users: default sort changes from SLA-based to `created_desc` (newest first)
- SLA sort preserved as `sort=smart` option
- Add `on_hold` and `engineer_visit` to all `open_statuses` lists

In `frontend/src/pages/TicketsPage.vue`:
- Default sort field for staff: `created_desc`
- Add new statuses to filter options and color maps

### 4. Email Threading Improvement

#### Outbound (backend/notifications/email.py):
1. Add ticket reference in HTML body footer:
   ```html
   <div style="color:#999;font-size:11px;border-top:1px solid #eee;padding-top:8px;margin-top:20px">
   --- Не удаляйте эту строку: PASS24-{ticket_id[:8]} ---
   </div>
   ```
2. Add email headers to `_send_email()`:
   - `Message-ID: <ticket-{ticket_id}@pass24servicedesk>`
   - `In-Reply-To: <ticket-{ticket_id}@pass24servicedesk>` (for replies)
   - `References: <ticket-{ticket_id}@pass24servicedesk>` (for replies)

#### Inbound (backend/notifications/inbound.py):
1. After tag-in-subject check, before Re: subject fallback:
   - Scan email body text for pattern `PASS24-([a-f0-9]{8})`
   - If found, match to ticket by prefix
2. Updated priority order: subject tag → body tag → Re: subject → new ticket

### 5. 2-Column Layout — Component Decomposition

#### Parent Shell: TicketDetailPage.vue (~200 lines)
- Route handler, ticket data loading, polling
- CSS Grid layout: `grid-template-columns: 1fr 380px`
- Responsive: `@media (max-width: 1024px)` → single column

#### Center Column Components (frontend/src/components/ticket/):

**TicketConversation.vue** (~250 lines)
- Merges `ticket.comments` + `ticket.events` into single chronological array
- Sorts by `created_at`
- Renders `TicketMessageBubble` for comments, `TicketTimelineDivider` for events
- Auto-scrolls to bottom on new messages

**TicketMessageBubble.vue** (~150 lines)
- Props: `comment: TicketComment`, `attachments: Attachment[]`, `isOwnMessage: boolean`, `isStaff: boolean`
- Client messages: left-aligned, light background
- Agent messages: right-aligned, blue/purple background
- Internal comments: yellow/amber background, lock icon, "Внутренний" badge
- Renders `TicketInlineAttachments` if attachments present

**TicketTimelineDivider.vue** (~40 lines)
- Small centered line with event text (e.g., "Статус изменён на in_progress")
- Timestamp on hover

**TicketComposeArea.vue** (~200 lines)
- Sticky at bottom of center column
- PrimeVue Textarea (auto-resize)
- Actions row: attach button (file picker), internal checkbox, template dropdown, send button
- Emits: `submit(text, isInternal)`, `upload(files)`

**TicketInlineAttachments.vue** (~120 lines)
- Horizontal flexbox of attachment chips
- Images: 80x80 thumbnail preview (via object URL or API endpoint)
- Others: file icon + filename + size
- Click emits `preview(attachment)` → parent opens preview dialog

#### Sidebar Components (frontend/src/components/ticket/):

**TicketSidebar.vue** (~100 lines)
- Container with PrimeVue Panel sections (toggleable)
- Groups: Actions, Info, Links, Events

**TicketStatusDropdown.vue** (~80 lines)
- PrimeVue Select with computed valid transitions from current status
- Options show: status label + color indicator
- Emits `changeStatus(newStatus)`

**TicketSlaProgress.vue** (~100 lines)
- PrimeVue ProgressBar showing SLA time remaining
- Color bands: green (<50%), yellow (50-75%), orange (75-90%), red (>90%)
- Labels: first response and resolution targets

**TicketAssignment.vue** (~80 lines)
- Current assignee display
- "Взять себе" button
- PrimeVue Select for assigning to other agents

**TicketContactInfo.vue** (~60 lines)
- Name, email (clickable), phone (clickable), company

**TicketObjectInfo.vue** (~50 lines)
- Object name, address, access point

**TicketClassification.vue** (~60 lines, staff-only)
- Product, type, source with labels

**TicketTechnicalInfo.vue** (~50 lines, staff-only)
- Device type, app version, error message (monospace)

**TicketLinkedArticles.vue** (~120 lines, staff-only)
- Extracted from current TicketDetailPage lines 1031-1111

**TicketLinkedProject.vue** (~80 lines, staff-only)
- Extracted from current TicketDetailPage lines 1113-1170

**TicketParentChild.vue** (~120 lines, staff-only)
- Extracted from current TicketDetailPage lines 1172-1246

**TicketEventsLog.vue** (~60 lines, staff-only)
- Collapsible audit trail

**TicketMacros.vue** (~50 lines, staff-only)
- Quick action buttons

#### Composables (frontend/src/composables/):

**useTicketConversation(ticket)**
- Returns: `timeline: ComputedRef<TimelineItem[]>` — merged and sorted comments + events
- Type: `TimelineItem = { type: 'comment' | 'event', data: TicketComment | TicketEvent, timestamp: Date }`

**useTicketTransitions(ticket)**
- Returns: `validTransitions: ComputedRef<TicketStatus[]>` — allowed next statuses from FSM
- Map: mirrors backend's `allowed` dict

**useTicketPreview()**
- Returns: `previewVisible, selectedAttachment, openPreview(attachment), closePreview(), downloadAttachment(attachment)`

**useAgentTools()**
- Returns: agents list, templates, macros, loadAll(), assignToMe(), runMacro()

### 6. Inline Attachments

#### Backend:
Add `comment_id: Optional[str]` to `Attachment` model (nullable, backward compatible).
Existing attachments keep `comment_id = null` → displayed at ticket level.
New attachments uploaded with a comment get `comment_id` set.

#### Frontend:
- `TicketMessageBubble` receives attachments filtered by `comment_id` match
- Unlinked attachments (comment_id = null) appended to the initial ticket description message (first bubble)
- Image thumbnails rendered inline (80x80, object-fit: cover, border-radius: 8px)
- Non-image files: icon chip (file type icon + name + formatted size)

## Files to Modify

### Backend (6 files + 1 new):
| File | Changes |
|------|---------|
| `backend/tickets/models.py` | +2 enum values, update FSM transitions, SLA pause for ON_HOLD |
| `backend/tickets/router.py` | Auto-status logic, default sort, open_statuses lists, status_order case |
| `backend/tickets/schemas.py` | Add comment_id to AttachmentRead |
| `backend/notifications/email.py` | +2 STATUS_LABELS, body reference, In-Reply-To headers |
| `backend/notifications/inbound.py` | Body-based ticket matching before subject fallback |
| `backend/tickets/sla_watcher.py` | Add ON_HOLD to monitored statuses |
| `migrations/versions/014_*.py` | NEW: enum extension + comment_id column |

### Frontend (3 modified + 22 new):
| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | +2 status values, comment_id on Attachment |
| `frontend/src/components/TicketStatusBadge.vue` | +2 statuses with colors/labels |
| `frontend/src/pages/TicketsPage.vue` | New status options, default sort, open counts |
| `frontend/src/pages/TicketDetailPage.vue` | REWRITE: 2-column shell |
| `frontend/src/components/ticket/*.vue` | NEW: 18 components |
| `frontend/src/composables/*.ts` | NEW: 4 composables |

## Implementation Phases

### Phase 1: Backend — New Statuses (low risk)
1. Add enum values to `TicketStatus`
2. Update `transition()` FSM dict
3. Update SLA pause logic for `ON_HOLD`
4. Create migration 014
5. Add STATUS_LABELS to email.py
6. Update `open_statuses` lists and `status_order` in router.py
7. Update `sla_watcher.py` to include ON_HOLD

### Phase 2: Backend — Auto-Status Fix (low risk)
1. Change `add_comment()`: NEW → IN_PROGRESS on agent response
2. Remove auto-transition to WAITING_FOR_USER on agent comment

### Phase 3: Frontend — Status Updates (low risk, depends on Phase 1-2)
1. Update `TicketStatus` type
2. Update `TicketStatusBadge.vue`
3. Update `TicketsPage.vue` (filters, sort, tabs)
4. Update status transition buttons temporarily in TicketDetailPage

### Phase 4: Backend — Email Threading (low risk, independent)
1. Add body reference to outbound emails
2. Add In-Reply-To / References headers
3. Add body-based matching to inbound processor

### Phase 5: Frontend — Layout Redesign (high risk, depends on Phase 1-3)
1. Create `frontend/src/components/ticket/` directory
2. Extract sidebar components (pure display, low risk)
3. Build `TicketStatusDropdown` replacing buttons
4. Build conversation components (new logic)
5. Build compose area
6. Create composables
7. Rewrite TicketDetailPage as 2-column shell

### Phase 6: Inline Attachments (medium risk, depends on Phase 5)
1. Add `comment_id` to Attachment model + migration
2. Update upload endpoint to accept comment_id
3. Frontend: group attachments by comment_id in message bubbles

## Verification

### Per-phase testing:
- **Phase 1**: Create ticket → manually change to on_hold → verify SLA pauses → change to engineer_visit → verify SLA continues
- **Phase 2**: Create ticket → agent comments → verify status is IN_PROGRESS (not WAITING_FOR_USER)
- **Phase 3**: Open ticket list → verify new statuses in filters → verify default sort is newest first
- **Phase 4**: Send email to support → reply with modified subject → verify reply threads to existing ticket via body match
- **Phase 5**: Open ticket detail → verify 2-column layout → post comment → verify bubble appears → resize to mobile → verify responsive
- **Phase 6**: Upload file during comment → verify thumbnail in message bubble → click → verify preview opens

### End-to-end:
1. Create ticket via web
2. Agent opens ticket → status is "new"
3. Agent comments → status changes to "in_progress" (not waiting_for_user)
4. Agent manually sets "engineer_visit" via dropdown
5. Agent sets "on_hold" → verify SLA pauses
6. Client replies via email → status returns to "in_progress" → conversation shows as threaded
7. Agent uploads file with comment → file appears inline in message bubble
8. View ticket list → sorted newest first → on_hold/engineer_visit show in "Open" tab
