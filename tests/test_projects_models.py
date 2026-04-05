"""Юнит-тесты для моделей проектов внедрения.

Тестируют бизнес-логику без БД:
- FSM переходов статусов проекта
- Пересчёт прогресса проекта и фазы
- Шаблоны (структура, количество фаз)
- Бизнес-методы Phase.start/complete и Task.complete
"""

from __future__ import annotations

import pytest

from backend.projects.models import (
    ImplementationProject,
    PhaseStatus,
    ProjectPhase,
    ProjectStatus,
    ProjectTask,
    ProjectType,
    TaskStatus,
)
from backend.projects.templates import PROJECT_TEMPLATES, get_template


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------


def _make_project(status: ProjectStatus = ProjectStatus.DRAFT) -> ImplementationProject:
    return ImplementationProject(
        code="PRJ-TEST-001",
        name="Тест ЖК",
        customer_id="customer-1",
        customer_company="УК Ромашка",
        object_name="ЖК Ромашка",
        project_type=ProjectType.RESIDENTIAL,
        status=status,
        created_by="admin-1",
    )


def _make_phase(
    project_id: str = "proj-1",
    status: PhaseStatus = PhaseStatus.PENDING,
    weight: int = 1,
    progress_pct: int = 0,
) -> ProjectPhase:
    return ProjectPhase(
        project_id=project_id,
        name="Test Phase",
        order_num=1,
        status=status,
        weight=weight,
        progress_pct=progress_pct,
    )


def _make_task(status: TaskStatus = TaskStatus.TODO) -> ProjectTask:
    return ProjectTask(
        phase_id="phase-1",
        project_id="proj-1",
        title="Test Task",
        status=status,
    )


# ---------------------------------------------------------------------------
# FSM проекта
# ---------------------------------------------------------------------------


def test_project_starts_in_draft():
    project = _make_project()
    assert project.status == ProjectStatus.DRAFT


def test_valid_transition_draft_to_planning():
    project = _make_project(ProjectStatus.DRAFT)
    event = project.transition(actor_id="admin-1", new_status=ProjectStatus.PLANNING)
    assert project.status == ProjectStatus.PLANNING
    assert event.event_type == "status_changed"
    assert "planning" in event.description


def test_valid_transition_planning_to_in_progress_sets_actual_start():
    project = _make_project(ProjectStatus.PLANNING)
    assert project.actual_start_date is None
    project.transition(actor_id="admin-1", new_status=ProjectStatus.IN_PROGRESS)
    assert project.status == ProjectStatus.IN_PROGRESS
    assert project.actual_start_date is not None


def test_transition_to_completed_sets_actual_end_and_100_pct():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    assert project.actual_end_date is None
    project.transition(actor_id="admin-1", new_status=ProjectStatus.COMPLETED)
    assert project.status == ProjectStatus.COMPLETED
    assert project.actual_end_date is not None
    assert project.progress_pct == 100


def test_invalid_transition_draft_to_completed_raises():
    project = _make_project(ProjectStatus.DRAFT)
    with pytest.raises(ValueError, match="Недопустимый переход"):
        project.transition(actor_id="admin-1", new_status=ProjectStatus.COMPLETED)


def test_invalid_transition_from_completed_raises():
    project = _make_project(ProjectStatus.COMPLETED)
    with pytest.raises(ValueError, match="Недопустимый переход"):
        project.transition(actor_id="admin-1", new_status=ProjectStatus.IN_PROGRESS)


def test_valid_transition_in_progress_to_on_hold_and_back():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    project.transition(actor_id="admin-1", new_status=ProjectStatus.ON_HOLD)
    assert project.status == ProjectStatus.ON_HOLD
    project.transition(actor_id="admin-1", new_status=ProjectStatus.IN_PROGRESS)
    assert project.status == ProjectStatus.IN_PROGRESS


def test_cancelled_is_terminal():
    project = _make_project(ProjectStatus.CANCELLED)
    with pytest.raises(ValueError, match="Недопустимый переход"):
        project.transition(actor_id="admin-1", new_status=ProjectStatus.PLANNING)


# ---------------------------------------------------------------------------
# Пересчёт прогресса проекта
# ---------------------------------------------------------------------------


def test_project_progress_zero_when_no_phases():
    project = _make_project()
    project.recalculate_progress()
    assert project.progress_pct == 0


def test_project_progress_weighted_average():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    # 2 фазы: weight=1 с progress=50, weight=1 с progress=0 → итого 25
    project.phases = [
        _make_phase(weight=1, progress_pct=50),
        _make_phase(weight=1, progress_pct=0),
    ]
    project.recalculate_progress()
    assert project.progress_pct == 25


def test_project_progress_with_different_weights():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    # weight=2 (100%), weight=1 (0%), weight=1 (0%) → 2*100 / 4 = 50
    project.phases = [
        _make_phase(weight=2, progress_pct=100),
        _make_phase(weight=1, progress_pct=0),
        _make_phase(weight=1, progress_pct=0),
    ]
    project.recalculate_progress()
    assert project.progress_pct == 50


def test_project_progress_skips_skipped_phases():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    # фаза 2 пропущена → должна не учитываться в расчёте
    project.phases = [
        _make_phase(weight=1, progress_pct=100),
        _make_phase(status=PhaseStatus.SKIPPED, weight=1, progress_pct=0),
    ]
    project.recalculate_progress()
    assert project.progress_pct == 100


def test_project_progress_all_phases_skipped_is_zero():
    project = _make_project(ProjectStatus.IN_PROGRESS)
    project.phases = [
        _make_phase(status=PhaseStatus.SKIPPED, weight=1, progress_pct=0),
        _make_phase(status=PhaseStatus.SKIPPED, weight=1, progress_pct=0),
    ]
    project.recalculate_progress()
    assert project.progress_pct == 0


# ---------------------------------------------------------------------------
# Пересчёт прогресса фазы
# ---------------------------------------------------------------------------


def test_phase_progress_zero_when_no_tasks():
    phase = _make_phase()
    phase.recalculate_progress()
    assert phase.progress_pct == 0


def test_phase_progress_3_of_6_done_equals_50():
    phase = _make_phase()
    phase.tasks = [
        _make_task(TaskStatus.DONE),
        _make_task(TaskStatus.DONE),
        _make_task(TaskStatus.DONE),
        _make_task(TaskStatus.TODO),
        _make_task(TaskStatus.IN_PROGRESS),
        _make_task(TaskStatus.TODO),
    ]
    phase.recalculate_progress()
    assert phase.progress_pct == 50


def test_phase_progress_ignores_cancelled_tasks():
    phase = _make_phase()
    # 2 done + 1 cancelled из 3 → (2 из 2 активных) = 100
    phase.tasks = [
        _make_task(TaskStatus.DONE),
        _make_task(TaskStatus.DONE),
        _make_task(TaskStatus.CANCELLED),
    ]
    phase.recalculate_progress()
    assert phase.progress_pct == 100


def test_phase_progress_all_cancelled_is_zero():
    phase = _make_phase()
    phase.tasks = [
        _make_task(TaskStatus.CANCELLED),
        _make_task(TaskStatus.CANCELLED),
    ]
    phase.recalculate_progress()
    assert phase.progress_pct == 0


# ---------------------------------------------------------------------------
# Phase.start() / complete()
# ---------------------------------------------------------------------------


def test_phase_start_transitions_to_in_progress():
    phase = _make_phase(status=PhaseStatus.PENDING)
    assert phase.actual_start_date is None
    event = phase.start(actor_id="agent-1")
    assert phase.status == PhaseStatus.IN_PROGRESS
    assert phase.actual_start_date is not None
    assert event.event_type == "phase_started"


def test_phase_start_fails_if_not_pending():
    phase = _make_phase(status=PhaseStatus.IN_PROGRESS)
    with pytest.raises(ValueError, match="PENDING"):
        phase.start(actor_id="agent-1")


def test_phase_complete_from_in_progress():
    phase = _make_phase(status=PhaseStatus.IN_PROGRESS)
    event = phase.complete(actor_id="agent-1")
    assert phase.status == PhaseStatus.COMPLETED
    assert phase.actual_end_date is not None
    assert phase.progress_pct == 100
    assert event.event_type == "phase_completed"


def test_phase_complete_fails_from_pending():
    phase = _make_phase(status=PhaseStatus.PENDING)
    with pytest.raises(ValueError, match="IN_PROGRESS/BLOCKED"):
        phase.complete(actor_id="agent-1")


# ---------------------------------------------------------------------------
# Task.complete()
# ---------------------------------------------------------------------------


def test_task_complete_sets_status_and_timestamps():
    task = _make_task(TaskStatus.TODO)
    assert task.completed_at is None
    task.complete(actor_id="agent-1")
    assert task.status == TaskStatus.DONE
    assert task.completed_at is not None
    assert task.completed_by == "agent-1"


def test_task_complete_is_idempotent():
    task = _make_task(TaskStatus.DONE)
    first_completed_at = task.completed_at
    task.complete(actor_id="agent-2")
    # Повторный вызов не меняет completed_by/completed_at
    assert task.completed_by != "agent-2"
    assert task.completed_at == first_completed_at


def test_task_complete_fails_on_cancelled():
    task = _make_task(TaskStatus.CANCELLED)
    with pytest.raises(ValueError, match="отменённую"):
        task.complete(actor_id="agent-1")


# ---------------------------------------------------------------------------
# Шаблоны
# ---------------------------------------------------------------------------


def test_all_project_types_have_templates():
    for project_type in ProjectType:
        template = get_template(project_type)
        assert template is not None
        assert len(template.phases) > 0


def test_residential_template_has_10_phases():
    template = PROJECT_TEMPLATES[ProjectType.RESIDENTIAL]
    assert len(template.phases) == 10
    assert template.phases[0].name == "Kickoff & Planning"
    assert template.phases[-1].name == "Handover"


def test_cameras_only_is_smallest_template():
    template = PROJECT_TEMPLATES[ProjectType.CAMERAS_ONLY]
    assert len(template.phases) == 5


def test_large_construction_is_biggest_template():
    template = PROJECT_TEMPLATES[ProjectType.LARGE_CONSTRUCTION]
    assert len(template.phases) == 12
    # У большой стройки должна быть отдельная фаза Quality Inspection
    phase_names = [p.name for p in template.phases]
    assert "Quality Inspection" in phase_names


def test_every_phase_has_at_least_one_task():
    for project_type, template in PROJECT_TEMPLATES.items():
        for phase in template.phases:
            assert len(phase.tasks) > 0, (
                f"В шаблоне {project_type.value} фаза {phase.name} без задач"
            )


def test_every_template_has_at_least_one_milestone():
    for project_type, template in PROJECT_TEMPLATES.items():
        milestones = [
            t for phase in template.phases for t in phase.tasks if t.is_milestone
        ]
        assert len(milestones) >= 1, (
            f"В шаблоне {project_type.value} нет milestone-задач"
        )


def test_phases_have_sequential_order():
    for project_type, template in PROJECT_TEMPLATES.items():
        orders = [p.order for p in template.phases]
        assert orders == list(range(1, len(template.phases) + 1)), (
            f"В шаблоне {project_type.value} порядок фаз не последовательный"
        )


def test_get_template_returns_correct_title():
    template = get_template(ProjectType.RESIDENTIAL)
    assert "ЖК" in template.title


def test_total_duration_is_sum_of_phase_durations():
    template = PROJECT_TEMPLATES[ProjectType.CAMERAS_ONLY]
    expected = sum(p.duration_days for p in template.phases)
    assert template.total_duration_days == expected
