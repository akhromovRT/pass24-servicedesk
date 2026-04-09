"""Endpoints для документов, команды, комментариев и событий проектов внедрения.

Выделены из главного router.py чтобы не разрастался. Регистрируется ПЕРЕД
основным projects_router в main.py, так как все пути имеют специфичный префикс
/projects/{project_id}/... и не конфликтуют с /projects/{id}.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from backend.auth.dependencies import get_current_user
from backend.auth.models import User, UserRole
from backend.database import get_session
from backend.projects.dependencies import (
    get_project_with_access,
    is_pass24_staff,
    require_admin,
    require_pass24_staff,
)
from backend.projects.models import (
    DocumentType,
    ProjectComment,
    ProjectDocument,
    ProjectEvent,
    ProjectTeamMember,
)
from backend.projects.schemas import (
    CommentCreate,
    CommentRead,
    DocumentRead,
    EventRead,
    LinkedTicket,
    TeamMemberCreate,
    TeamMemberRead,
    TicketLinkRequest,
)
from backend.tickets.models import Ticket

PROJECTS_UPLOAD_DIR = Path("/app/data/projects")
MAX_DOC_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_DOC_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/plain",
}

router = APIRouter(prefix="/projects", tags=["projects-workspace"])


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


@router.post(
    "/{project_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    project_id: str,
    file: UploadFile,
    document_type: DocumentType = DocumentType.OTHER,
    name: Optional[str] = None,
    phase_id: Optional[str] = None,
    task_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> DocumentRead:
    """Загрузить документ. PM может загружать в свой проект, PASS24 в любой. Макс. 20 МБ."""
    # RBAC через get_project_with_access
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    if file.content_type not in ALLOWED_DOC_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимый тип файла (разрешены: PDF, DOCX, XLSX, JPG, PNG, TXT)",
        )

    content = await file.read()
    if len(content) > MAX_DOC_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл слишком большой (макс. 20 МБ)",
        )

    file_id = str(uuid.uuid4())
    ext = Path(file.filename or "file").suffix
    storage_path = f"{project_id}/{file_id}{ext}"
    full_path = PROJECTS_UPLOAD_DIR / storage_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(content)

    document = ProjectDocument(
        project_id=project_id,
        phase_id=phase_id,
        task_id=task_id,
        document_type=document_type,
        name=name or file.filename or "Документ",
        filename=file.filename or "file",
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        storage_path=storage_path,
        uploaded_by=str(current_user.id),
    )
    session.add(document)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="document_uploaded",
            description=f"Загружен документ «{document.name}» ({document_type.value})",
        )
    )
    await session.commit()
    await session.refresh(document)
    return DocumentRead.model_validate(document)


@router.get("/{project_id}/documents", response_model=List[DocumentRead])
async def list_documents(
    project_id: str,
    document_type: Optional[str] = Query(default=None),
    phase_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[DocumentRead]:
    """Список документов проекта с опциональной фильтрацией."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    query = select(ProjectDocument).where(ProjectDocument.project_id == project_id)
    if document_type:
        query = query.where(ProjectDocument.document_type == document_type)
    if phase_id:
        query = query.where(ProjectDocument.phase_id == phase_id)
    query = query.order_by(ProjectDocument.created_at.desc())

    result = await session.execute(query)
    documents = result.scalars().all()
    return [DocumentRead.model_validate(d) for d in documents]


@router.get("/{project_id}/documents/{document_id}/download")
async def download_document(
    project_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Скачать документ."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    document = await session.get(ProjectDocument, document_id)
    if document is None or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")

    file_path = PROJECTS_UPLOAD_DIR / document.storage_path
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Файл не найден на сервере",
        )

    return FileResponse(
        path=str(file_path),
        filename=document.filename,
        media_type=document.content_type,
    )


@router.delete("/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_document(
    project_id: str,
    document_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> None:
    """Удалить документ (только команда PASS24)."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    document = await session.get(ProjectDocument, document_id)
    if document is None or document.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ не найден")

    # Удаление файла с диска (не фатально если нет)
    file_path = PROJECTS_UPLOAD_DIR / document.storage_path
    if file_path.is_file():
        try:
            file_path.unlink()
        except OSError:
            pass

    await session.delete(document)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="document_deleted",
            description=f"Удалён документ «{document.name}»",
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Team
# ---------------------------------------------------------------------------


@router.get("/{project_id}/team", response_model=List[TeamMemberRead])
async def list_team(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[TeamMemberRead]:
    """Состав команды проекта с данными пользователей."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    result = await session.execute(
        select(ProjectTeamMember, User)
        .join(User, User.id == ProjectTeamMember.user_id, isouter=True)
        .where(ProjectTeamMember.project_id == project_id)
        .order_by(ProjectTeamMember.added_at)
    )
    rows = result.all()

    team: List[TeamMemberRead] = []
    for member, user in rows:
        read = TeamMemberRead.model_validate(member)
        if user is not None:
            read.user_name = user.full_name
            read.user_email = user.email
        team.append(read)
    return team


@router.post(
    "/{project_id}/team",
    response_model=TeamMemberRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_team_member(
    project_id: str,
    payload: TeamMemberCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> TeamMemberRead:
    """Добавить участника в команду проекта (только admin)."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    # Проверка на дубликат
    existing = await session.execute(
        select(ProjectTeamMember).where(
            ProjectTeamMember.project_id == project_id,
            ProjectTeamMember.user_id == payload.user_id,
            ProjectTeamMember.team_role == payload.team_role,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Участник с такой ролью уже добавлен",
        )

    # Проверка существования user (не падаем, если нет — хранение идемпотентно)
    user = await session.get(User, payload.user_id)

    member = ProjectTeamMember(
        project_id=project_id,
        user_id=payload.user_id,
        team_role=payload.team_role,
        is_primary=payload.is_primary,
        added_by=str(current_user.id),
    )
    session.add(member)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="team_member_added",
            description=(
                f"Добавлен участник {user.full_name if user else payload.user_id} "
                f"({payload.team_role.value})"
            ),
        )
    )
    await session.commit()
    await session.refresh(member)

    read = TeamMemberRead.model_validate(member)
    if user:
        read.user_name = user.full_name
        read.user_email = user.email
    return read


@router.delete("/{project_id}/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def remove_team_member(
    project_id: str,
    member_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_admin),
) -> None:
    """Удалить участника команды (только admin)."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    member = await session.get(ProjectTeamMember, member_id)
    if member is None or member.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден"
        )

    await session.delete(member)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="team_member_removed",
            description=f"Удалён участник {member.user_id}",
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


@router.get("/{project_id}/comments", response_model=List[CommentRead])
async def list_comments(
    project_id: str,
    task_id: Optional[str] = Query(default=None),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[CommentRead]:
    """Список комментариев. PM не видит is_internal=true."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    query = select(ProjectComment).where(ProjectComment.project_id == project_id)
    if task_id:
        query = query.where(ProjectComment.task_id == task_id)

    # PM не должен видеть internal-комментарии
    if not is_pass24_staff(current_user):
        query = query.where(ProjectComment.is_internal == False)  # noqa: E712

    query = query.order_by(ProjectComment.created_at)
    result = await session.execute(query)
    comments = result.scalars().all()
    return [CommentRead.model_validate(c) for c in comments]


@router.post(
    "/{project_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_comment(
    project_id: str,
    payload: CommentCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    """Добавить комментарий к проекту или задаче."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    # PM не может ставить is_internal=true
    is_internal = payload.is_internal
    if is_internal and not is_pass24_staff(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только команда PASS24 может оставлять внутренние комментарии",
        )

    # Проверка task_id принадлежит проекту
    if payload.task_id:
        from backend.projects.models import ProjectTask
        task = await session.get(ProjectTask, payload.task_id)
        if task is None or task.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Задача не найдена",
            )

    comment = ProjectComment(
        project_id=project_id,
        task_id=payload.task_id,
        author_id=str(current_user.id),
        author_name=current_user.full_name,
        text=payload.text,
        is_internal=is_internal,
    )
    session.add(comment)
    await session.commit()
    await session.refresh(comment)
    return CommentRead.model_validate(comment)


# ---------------------------------------------------------------------------
# Events (audit log)
# ---------------------------------------------------------------------------


@router.get("/{project_id}/events", response_model=List[EventRead])
async def list_events(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[EventRead]:
    """Лента событий проекта (новые сверху)."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    result = await session.execute(
        select(ProjectEvent)
        .where(ProjectEvent.project_id == project_id)
        .order_by(ProjectEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [EventRead.model_validate(e) for e in events]


# ---------------------------------------------------------------------------
# Ticket linking
# ---------------------------------------------------------------------------


@router.get("/{project_id}/tickets", response_model=List[LinkedTicket])
async def list_linked_tickets(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> List[LinkedTicket]:
    """Список тикетов, связанных с проектом."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    result = await session.execute(
        select(Ticket)
        .where(Ticket.implementation_project_id == project_id)
        .order_by(
            Ticket.is_implementation_blocker.desc(),
            Ticket.created_at.desc(),
        )
    )
    tickets = result.scalars().all()
    return [LinkedTicket.model_validate(t) for t in tickets]


@router.post("/{project_id}/link-ticket", response_model=LinkedTicket)
async def link_ticket(
    project_id: str,
    payload: TicketLinkRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> LinkedTicket:
    """Связать тикет с проектом. Только для команды PASS24."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    ticket = await session.get(Ticket, payload.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Тикет не найден")

    ticket.implementation_project_id = project_id
    ticket.is_implementation_blocker = payload.is_blocker
    session.add(ticket)

    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="ticket_linked",
            description=(
                f"К проекту привязан тикет «{ticket.title}»"
                f"{' (блокер)' if payload.is_blocker else ''}"
            ),
        )
    )
    await session.commit()
    await session.refresh(ticket)
    return LinkedTicket.model_validate(ticket)


@router.post("/{project_id}/unlink-ticket/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def unlink_ticket(
    project_id: str,
    ticket_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_pass24_staff),
) -> None:
    """Отвязать тикет от проекта."""
    _ = await get_project_with_access(
        project_id, session=session, current_user=current_user
    )

    ticket = await session.get(Ticket, ticket_id)
    if ticket is None or ticket.implementation_project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Связь тикета с проектом не найдена",
        )

    ticket.implementation_project_id = None
    ticket.is_implementation_blocker = False
    session.add(ticket)
    session.add(
        ProjectEvent(
            project_id=project_id,
            actor_id=str(current_user.id),
            event_type="ticket_unlinked",
            description=f"Тикет «{ticket.title}» отвязан от проекта",
        )
    )
    await session.commit()


# ---------------------------------------------------------------------------
# Approvals — утверждение фаз клиентом
# ---------------------------------------------------------------------------

from backend.projects.models import ProjectApproval, ApprovalStatus, PhaseStatus
from pydantic import BaseModel as PydanticBaseModel


class ApprovalRead(PydanticBaseModel):
    id: str
    project_id: str
    phase_id: str
    status: str
    requested_by: str
    reviewed_by: Optional[str] = None
    feedback: Optional[str] = None
    requested_at: str
    reviewed_at: Optional[str] = None
    model_config = {"from_attributes": True}


class RejectPayload(PydanticBaseModel):
    feedback: str


@router.get("/{project_id}/approvals", response_model=List[ApprovalRead])
async def list_approvals(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _project=Depends(get_project_with_access),
):
    """Список всех утверждений проекта."""
    result = await session.execute(
        select(ProjectApproval)
        .where(ProjectApproval.project_id == project_id)
        .order_by(ProjectApproval.requested_at.desc())
    )
    approvals = result.scalars().all()
    return [ApprovalRead.model_validate(a) for a in approvals]


@router.post("/{project_id}/phases/{phase_id}/request-approval", response_model=ApprovalRead, status_code=status.HTTP_201_CREATED)
async def request_approval(
    project_id: str,
    phase_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_pass24_staff),
):
    """Запрос утверждения завершённой фазы у клиента."""
    from backend.projects.models import ProjectPhase

    # Проверяем фазу
    result = await session.execute(
        select(ProjectPhase).where(ProjectPhase.id == phase_id, ProjectPhase.project_id == project_id)
    )
    phase = result.scalar_one_or_none()
    if not phase:
        raise HTTPException(status_code=404, detail="Фаза не найдена")
    if phase.status != PhaseStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Фаза должна быть завершена перед запросом утверждения")

    # Проверяем нет ли уже pending approval
    existing = await session.execute(
        select(ProjectApproval).where(
            ProjectApproval.phase_id == phase_id,
            ProjectApproval.status == "pending",
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Утверждение уже запрошено")

    approval = ProjectApproval(
        project_id=project_id,
        phase_id=phase_id,
        requested_by=str(current_user.id),
    )
    session.add(approval)

    session.add(ProjectEvent(
        project_id=project_id,
        actor_id=str(current_user.id),
        event_type="approval_requested",
        description=f"Запрошено утверждение фазы «{phase.name}»",
    ))
    await session.commit()
    await session.refresh(approval)

    # Email клиенту
    from backend.projects.models import ImplementationProject
    proj_result = await session.execute(
        select(ImplementationProject).where(ImplementationProject.id == project_id)
    )
    project = proj_result.scalar_one_or_none()
    if project:
        from backend.auth.models import User as AuthUser
        client_result = await session.execute(
            select(AuthUser).where(AuthUser.id == project.customer_id)
        )
        client = client_result.scalar_one_or_none()
        if client:
            from backend.notifications.email import _send_email
            await _send_email(
                to=client.email,
                subject=f"Этап «{phase.name}» завершён — подтвердите",
                html_body=f"""
                <div style="font-family: -apple-system, Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                    <div style="background: #0f172a; color: #f8fafc; padding: 16px 24px; border-radius: 8px 8px 0 0;">
                        <strong>PASS24 Service Desk</strong>
                    </div>
                    <div style="padding: 24px; background: #fff; border: 1px solid #e2e8f0; border-top: none; border-radius: 0 0 8px 8px;">
                        <h2 style="margin: 0 0 16px; color: #1e293b;">Этап завершён — требуется подтверждение</h2>
                        <p style="color: #475569;">Проект: <strong>{project.name}</strong></p>
                        <p style="color: #475569;">Этап: <strong>{phase.name}</strong></p>
                        <p style="color: #475569;">Пожалуйста, войдите на портал и подтвердите завершение этапа.</p>
                        <div style="margin-top: 20px; text-align: center;">
                            <a href="https://support.pass24pro.ru/projects/{project_id}" style="display:inline-block;background:#0f172a;color:#fff;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:500;">Открыть проект</a>
                        </div>
                    </div>
                </div>
                """,
            )

    return ApprovalRead.model_validate(approval)


@router.post("/{project_id}/approvals/{approval_id}/approve", response_model=ApprovalRead)
async def approve_phase(
    project_id: str,
    approval_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _project=Depends(get_project_with_access),
):
    """Клиент утверждает завершение фазы."""
    result = await session.execute(
        select(ProjectApproval).where(ProjectApproval.id == approval_id, ProjectApproval.project_id == project_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Утверждение не найдено")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Утверждение уже обработано")

    from datetime import datetime
    approval.status = "approved"
    approval.reviewed_by = str(current_user.id)
    approval.reviewed_at = datetime.utcnow()
    session.add(approval)

    session.add(ProjectEvent(
        project_id=project_id,
        actor_id=str(current_user.id),
        event_type="approval_approved",
        description=f"Фаза утверждена клиентом",
    ))
    await session.commit()
    await session.refresh(approval)
    return ApprovalRead.model_validate(approval)


@router.post("/{project_id}/approvals/{approval_id}/reject", response_model=ApprovalRead)
async def reject_phase(
    project_id: str,
    approval_id: str,
    payload: RejectPayload,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _project=Depends(get_project_with_access),
):
    """Клиент отклоняет завершение фазы (с комментарием)."""
    result = await session.execute(
        select(ProjectApproval).where(ProjectApproval.id == approval_id, ProjectApproval.project_id == project_id)
    )
    approval = result.scalar_one_or_none()
    if not approval:
        raise HTTPException(status_code=404, detail="Утверждение не найдено")
    if approval.status != "pending":
        raise HTTPException(status_code=400, detail="Утверждение уже обработано")

    from datetime import datetime
    approval.status = "rejected"
    approval.reviewed_by = str(current_user.id)
    approval.feedback = payload.feedback
    approval.reviewed_at = datetime.utcnow()
    session.add(approval)

    # Вернуть фазу в in_progress
    from backend.projects.models import ProjectPhase
    phase_result = await session.execute(
        select(ProjectPhase).where(ProjectPhase.id == approval.phase_id)
    )
    phase = phase_result.scalar_one_or_none()
    if phase:
        phase.status = PhaseStatus.IN_PROGRESS
        session.add(phase)

    session.add(ProjectEvent(
        project_id=project_id,
        actor_id=str(current_user.id),
        event_type="approval_rejected",
        description=f"Фаза отклонена клиентом: {payload.feedback}",
    ))
    await session.commit()
    await session.refresh(approval)
    return ApprovalRead.model_validate(approval)


# ---------------------------------------------------------------------------
# Риски проекта
# ---------------------------------------------------------------------------

from backend.projects.models import ProjectRisk


class RiskCreate(PydanticBaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "medium"
    probability: str = "medium"
    impact: str = "medium"
    mitigation_plan: Optional[str] = None
    owner_id: Optional[str] = None


class RiskUpdate(PydanticBaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[str] = None
    probability: Optional[str] = None
    impact: Optional[str] = None
    mitigation_plan: Optional[str] = None
    owner_id: Optional[str] = None
    status: Optional[str] = None


class RiskRead(PydanticBaseModel):
    id: str
    project_id: str
    title: str
    description: Optional[str] = None
    severity: str
    probability: str
    impact: str
    mitigation_plan: Optional[str] = None
    owner_id: Optional[str] = None
    status: str
    created_by: str
    created_at: str
    updated_at: str
    model_config = {"from_attributes": True}


@router.get("/{project_id}/risks", response_model=List[RiskRead])
async def list_risks(
    project_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_pass24_staff),
):
    """Список рисков проекта (только для staff)."""
    result = await session.execute(
        select(ProjectRisk)
        .where(ProjectRisk.project_id == project_id)
        .order_by(ProjectRisk.created_at.desc())
    )
    return [RiskRead.model_validate(r) for r in result.scalars().all()]


@router.post("/{project_id}/risks", response_model=RiskRead, status_code=status.HTTP_201_CREATED)
async def create_risk(
    project_id: str,
    payload: RiskCreate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_pass24_staff),
):
    """Создать риск проекта."""
    risk = ProjectRisk(
        project_id=project_id,
        title=payload.title,
        description=payload.description,
        severity=payload.severity,
        probability=payload.probability,
        impact=payload.impact,
        mitigation_plan=payload.mitigation_plan,
        owner_id=payload.owner_id,
        created_by=str(current_user.id),
    )
    session.add(risk)
    session.add(ProjectEvent(
        project_id=project_id,
        actor_id=str(current_user.id),
        event_type="risk_created",
        description=f"Риск «{payload.title}» создан (severity: {payload.severity})",
    ))
    await session.commit()
    await session.refresh(risk)
    return RiskRead.model_validate(risk)


@router.put("/{project_id}/risks/{risk_id}", response_model=RiskRead)
async def update_risk(
    project_id: str,
    risk_id: str,
    payload: RiskUpdate,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_pass24_staff),
):
    """Обновить риск."""
    result = await session.execute(
        select(ProjectRisk).where(ProjectRisk.id == risk_id, ProjectRisk.project_id == project_id)
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Риск не найден")

    from datetime import datetime
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(risk, field, value)
    risk.updated_at = datetime.utcnow()
    session.add(risk)
    await session.commit()
    await session.refresh(risk)
    return RiskRead.model_validate(risk)


@router.delete("/{project_id}/risks/{risk_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_risk(
    project_id: str,
    risk_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
    _=Depends(require_pass24_staff),
):
    """Удалить риск."""
    result = await session.execute(
        select(ProjectRisk).where(ProjectRisk.id == risk_id, ProjectRisk.project_id == project_id)
    )
    risk = result.scalar_one_or_none()
    if not risk:
        raise HTTPException(status_code=404, detail="Риск не найден")
    await session.delete(risk)
    await session.commit()
