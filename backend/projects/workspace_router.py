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


@router.delete("/{project_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.delete("/{project_id}/team/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
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


@router.post("/{project_id}/unlink-ticket/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
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
