"""Implementation projects module: 7 new tables + 2 fields in tickets.

Creates the full domain for managing client onboarding/implementation projects:
projects, phases, tasks, documents, team members, events, comments.
Also adds optional link from tickets to projects.

Revision ID: 010
Revises: 009
Create Date: 2026-04-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- implementation_projects ---
    op.create_table(
        "implementation_projects",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("customer_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("customer_company", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("object_name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("object_address", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column("project_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="residential"),
        sa.Column("status", sa.VARCHAR(), nullable=False, server_default="draft"),
        sa.Column("contract_number", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("contract_signed_at", sa.Date(), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("planned_end_date", sa.Date(), nullable=True),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("manager_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("notes", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=True),
        sa.Column("created_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_implementation_projects_code", "implementation_projects", ["code"], unique=True)
    op.create_index("ix_implementation_projects_name", "implementation_projects", ["name"])
    op.create_index("ix_implementation_projects_customer_id", "implementation_projects", ["customer_id"])
    op.create_index("ix_implementation_projects_object_name", "implementation_projects", ["object_name"])
    op.create_index("ix_implementation_projects_project_type", "implementation_projects", ["project_type"])
    op.create_index("ix_implementation_projects_status", "implementation_projects", ["status"])
    op.create_index("ix_implementation_projects_manager_id", "implementation_projects", ["manager_id"])

    # --- project_phases ---
    op.create_table(
        "project_phases",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column("order_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.VARCHAR(), nullable=False, server_default="pending"),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("planned_duration_days", sa.Integer(), nullable=True),
        sa.Column("planned_start_date", sa.Date(), nullable=True),
        sa.Column("planned_end_date", sa.Date(), nullable=True),
        sa.Column("actual_start_date", sa.Date(), nullable=True),
        sa.Column("actual_end_date", sa.Date(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_project_phases_project_id", "project_phases", ["project_id"])
    op.create_index("ix_project_phases_status", "project_phases", ["status"])

    # --- project_tasks ---
    op.create_table(
        "project_tasks",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("phase_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=2000), nullable=True),
        sa.Column("status", sa.VARCHAR(), nullable=False, server_default="todo"),
        sa.Column("priority", sa.VARCHAR(), nullable=False, server_default="normal"),
        sa.Column("assignee_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("order_num", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_milestone", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("estimated_hours", sa.Integer(), nullable=True),
        sa.Column("actual_hours", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("completed_by", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["phase_id"], ["project_phases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_project_tasks_phase_id", "project_tasks", ["phase_id"])
    op.create_index("ix_project_tasks_project_id", "project_tasks", ["project_id"])
    op.create_index("ix_project_tasks_assignee_id", "project_tasks", ["assignee_id"])
    op.create_index("ix_project_tasks_status", "project_tasks", ["status"])
    op.create_index("ix_project_tasks_due_date", "project_tasks", ["due_date"])

    # --- project_documents ---
    op.create_table(
        "project_documents",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("phase_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("task_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("document_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="other"),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(length=512), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("uploaded_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["phase_id"], ["project_phases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_project_documents_project_id", "project_documents", ["project_id"])
    op.create_index("ix_project_documents_phase_id", "project_documents", ["phase_id"])
    op.create_index("ix_project_documents_task_id", "project_documents", ["task_id"])
    op.create_index("ix_project_documents_document_type", "project_documents", ["document_type"])

    # --- project_team_members ---
    op.create_table(
        "project_team_members",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("user_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("team_role", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="installer"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("added_by", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "user_id", "team_role", name="uq_team_member_role"),
    )
    op.create_index("ix_project_team_members_project_id", "project_team_members", ["project_id"])
    op.create_index("ix_project_team_members_user_id", "project_team_members", ["user_id"])
    op.create_index("ix_project_team_members_team_role", "project_team_members", ["team_role"])

    # --- project_events ---
    op.create_table(
        "project_events",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("actor_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("event_type", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=False),
        sa.Column("meta_json", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])
    op.create_index("ix_project_events_event_type", "project_events", ["event_type"])
    op.create_index("ix_project_events_created_at", "project_events", ["created_at"])

    # --- project_comments ---
    op.create_table(
        "project_comments",
        sa.Column("id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("task_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("author_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("author_name", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=False, server_default=""),
        sa.Column("text", sqlmodel.sql.sqltypes.AutoString(length=4000), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["project_id"], ["implementation_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_project_comments_project_id", "project_comments", ["project_id"])
    op.create_index("ix_project_comments_task_id", "project_comments", ["task_id"])

    # --- ALTER tickets: add link to implementation_project ---
    op.add_column(
        "tickets",
        sa.Column("implementation_project_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.add_column(
        "tickets",
        sa.Column("is_implementation_blocker", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index(
        "ix_tickets_implementation_project_id",
        "tickets",
        ["implementation_project_id"],
    )
    op.create_index(
        "ix_tickets_is_implementation_blocker",
        "tickets",
        ["is_implementation_blocker"],
    )
    op.create_foreign_key(
        "fk_tickets_implementation_project",
        "tickets",
        "implementation_projects",
        ["implementation_project_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ALTER tickets: remove link fields
    op.drop_constraint("fk_tickets_implementation_project", "tickets", type_="foreignkey")
    op.drop_index("ix_tickets_is_implementation_blocker", table_name="tickets")
    op.drop_index("ix_tickets_implementation_project_id", table_name="tickets")
    op.drop_column("tickets", "is_implementation_blocker")
    op.drop_column("tickets", "implementation_project_id")

    # Drop tables in reverse order (respecting FK)
    op.drop_index("ix_project_comments_task_id", table_name="project_comments")
    op.drop_index("ix_project_comments_project_id", table_name="project_comments")
    op.drop_table("project_comments")

    op.drop_index("ix_project_events_created_at", table_name="project_events")
    op.drop_index("ix_project_events_event_type", table_name="project_events")
    op.drop_index("ix_project_events_project_id", table_name="project_events")
    op.drop_table("project_events")

    op.drop_index("ix_project_team_members_team_role", table_name="project_team_members")
    op.drop_index("ix_project_team_members_user_id", table_name="project_team_members")
    op.drop_index("ix_project_team_members_project_id", table_name="project_team_members")
    op.drop_table("project_team_members")

    op.drop_index("ix_project_documents_document_type", table_name="project_documents")
    op.drop_index("ix_project_documents_task_id", table_name="project_documents")
    op.drop_index("ix_project_documents_phase_id", table_name="project_documents")
    op.drop_index("ix_project_documents_project_id", table_name="project_documents")
    op.drop_table("project_documents")

    op.drop_index("ix_project_tasks_due_date", table_name="project_tasks")
    op.drop_index("ix_project_tasks_status", table_name="project_tasks")
    op.drop_index("ix_project_tasks_assignee_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_project_id", table_name="project_tasks")
    op.drop_index("ix_project_tasks_phase_id", table_name="project_tasks")
    op.drop_table("project_tasks")

    op.drop_index("ix_project_phases_status", table_name="project_phases")
    op.drop_index("ix_project_phases_project_id", table_name="project_phases")
    op.drop_table("project_phases")

    op.drop_index("ix_implementation_projects_manager_id", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_status", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_project_type", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_object_name", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_customer_id", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_name", table_name="implementation_projects")
    op.drop_index("ix_implementation_projects_code", table_name="implementation_projects")
    op.drop_table("implementation_projects")
