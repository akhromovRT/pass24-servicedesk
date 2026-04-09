# v0.8 Phase 2: Approvals, Risk Tracker, Template Editor, Project Analytics

## Context

v0.8 Phase 1 (agent interface redesign) is complete. Phase 2 adds 4 features to the Implementation Projects module, delivered sequentially.

## Feature 1: Approvals Workflow

### Purpose
When a PASS24 manager completes a project phase, the client (property_manager) must approve/reject the completion through the portal.

### Data Model
New table `project_approvals`:
- `id` (UUID, PK)
- `project_id` (FK → implementation_projects)
- `phase_id` (FK → project_phases)
- `status`: enum `pending` | `approved` | `rejected`
- `requested_by` (FK → users) — PASS24 manager who requested approval
- `reviewed_by` (FK → users, nullable) — client who approved/rejected
- `feedback` (text, nullable) — client comment on rejection
- `requested_at` (datetime)
- `reviewed_at` (datetime, nullable)

### Business Logic
1. Manager completes phase (status → completed) → auto-creates ProjectApproval with status=pending
2. Client receives email: "Phase X completed — please review"
3. Client sees orange badge "Ожидает подтверждения" on the phase card
4. Client clicks "Утвердить" or "Отклонить" (with feedback)
5. On rejection: phase returns to in_progress, manager gets email with reason

### API Endpoints
- `POST /projects/{id}/phases/{phase_id}/request-approval` — manager requests
- `POST /projects/{id}/approvals/{approval_id}/approve` — client approves
- `POST /projects/{id}/approvals/{approval_id}/reject` — client rejects (body: {feedback})
- `GET /projects/{id}/approvals` — list all approvals

### UI Changes
- Phase card: orange badge "Ожидает подтверждения" when approval pending
- For property_manager: "Утвердить" / "Отклонить" buttons on completed phases
- For staff: sees approval status + feedback
- Email notifications: on request, approve, reject

### Migration
- `016_project_approvals.py`: create `project_approvals` table

---

## Feature 2: Risk Tracker

### Purpose
Track and manage project risks with severity levels and mitigation plans.

### Data Model
New table `project_risks`:
- `id` (UUID, PK)
- `project_id` (FK → implementation_projects)
- `title` (string, 200)
- `description` (text, nullable)
- `severity`: enum `low` | `medium` | `high` | `critical`
- `probability`: enum `low` | `medium` | `high`
- `impact`: enum `low` | `medium` | `high`
- `mitigation_plan` (text, nullable)
- `owner_id` (FK → users, nullable)
- `status`: enum `open` | `mitigated` | `occurred` | `closed`
- `created_by` (FK → users)
- `created_at`, `updated_at`

### API Endpoints
- `GET /projects/{id}/risks` — list project risks
- `POST /projects/{id}/risks` — create risk
- `PUT /projects/{id}/risks/{risk_id}` — update risk
- `DELETE /projects/{id}/risks/{risk_id}` — delete risk

### UI Changes
- New "Риски" tab on ProjectDetailPage
- Risk cards with color-coded severity (green/yellow/orange/red)
- Create/edit dialog
- Risk summary badge on project list (count of open high/critical risks)

### Migration
- `017_project_risks.py`: create `project_risks` table

---

## Feature 3: Template Editor

### Purpose
Allow admins to create/edit/clone project templates through the Settings page instead of hardcoded Python constants.

### Data Model
New table `project_templates_db`:
- `id` (UUID, PK)
- `project_type` (string, unique) — maps to ProjectType enum
- `title` (string, 200)
- `description` (text)
- `total_duration_days` (int)
- `phases_json` (JSON) — array of phase definitions with tasks
- `is_active` (bool, default true)
- `created_by` (FK → users)
- `created_at`, `updated_at`

### Business Logic
- On startup: if no templates in DB, seed from existing Python constants
- Project creation uses DB templates instead of Python constants
- Admin can create/edit/clone/deactivate templates
- Deactivated templates not shown in creation form but existing projects keep their data

### API Endpoints
- `GET /projects/templates` — list active templates (already exists, modify to read from DB)
- `POST /projects/templates` — create template (admin only)
- `PUT /projects/templates/{id}` — update template (admin only)
- `DELETE /projects/templates/{id}` — deactivate template (admin only)

### UI Changes
- New section in SettingsPage: "Шаблоны проектов"
- Template list with edit/clone/deactivate actions
- Edit dialog: template name, phases, tasks (inline editing)

### Migration
- `018_project_templates_db.py`: create table + seed from Python constants

---

## Feature 4: Project Analytics Dashboard

### Purpose
Provide metrics and charts for PASS24 staff to monitor implementation project performance.

### Metrics
- **Time-to-Go-Live**: average days from project creation to completion, by project type
- **On-Time Delivery Rate**: % of projects completed before planned_end_date
- **Health Score**: composite score based on phase delays, open risks, pending approvals
- **Active Projects by Type**: pie chart
- **Phase Duration vs Plan**: bar chart comparing planned vs actual duration

### API Endpoint
- `GET /projects/analytics` — returns all metrics (staff only)

### UI Changes
- New page `/projects/analytics` (linked from Projects menu)
- ECharts charts: bar, pie, line
- Summary cards at top (like AgentDashboardPage)

### Migration
- None needed (computed from existing data)

---

## Implementation Order
1. Approvals (migration 016 + backend + frontend)
2. Risks (migration 017 + backend + frontend)
3. Templates (migration 018 + backend + frontend)
4. Analytics (backend endpoint + frontend page)

## Verification
- Approvals: complete phase → client sees badge → approve/reject → email sent
- Risks: create risk → edit severity → close → badge on project list
- Templates: create template → use in project creation → edit → clone
- Analytics: open /projects/analytics → charts render with real data
