"""Background task: send a CSAT nudge over Telegram 24h after a ticket is resolved.

Fires once per ticket. Uses ``satisfaction_requested_at`` as the sent-flag:
the ``transition()`` method sets it equal to ``resolved_at`` on resolve; the
scheduler advances it to the send time, which excludes the row from future
runs. No schema change required.

Runs every hour. A one-hour drift in delivery is acceptable for a satisfaction
survey; waking more often would spend cycles scanning the same resolved set.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from sqlmodel import select

from backend.auth.models import User
from backend.database import async_session_factory
from backend.tickets.models import Ticket, TicketStatus

logger = logging.getLogger(__name__)


CHECK_INTERVAL_SECONDS = 3600  # 1 hour
MIN_AGE_HOURS = 24


async def _due_tickets() -> list[tuple[Ticket, User | None]]:
    """Fetch tickets eligible for a CSAT nudge and their creators."""
    cutoff = datetime.utcnow() - timedelta(hours=MIN_AGE_HOURS)
    async with async_session_factory() as session:
        stmt = (
            select(Ticket)
            .where(
                Ticket.status == TicketStatus.RESOLVED.value,
                Ticket.resolved_at.is_not(None),
                Ticket.resolved_at < cutoff,
                Ticket.satisfaction_rating.is_(None),
                # transition() sets satisfaction_requested_at == resolved_at on resolve.
                # Once the scheduler sends a nudge, it advances the timestamp,
                # excluding the ticket from future runs.
                Ticket.satisfaction_requested_at <= Ticket.resolved_at,
            )
            .limit(200)
        )
        tickets = list((await session.execute(stmt)).scalars().all())

        pairs: list[tuple[Ticket, User | None]] = []
        for ticket in tickets:
            user: User | None = None
            if ticket.creator_id:
                user = (await session.execute(
                    select(User).where(User.id == ticket.creator_id)
                )).scalar_one_or_none()
            pairs.append((ticket, user))
        return pairs


async def _send_nudge(ticket: Ticket, user: User) -> None:
    """Send CSAT prompt to a single linked user and mark the ticket."""
    from backend.telegram.services.notify import notify_telegram_csat_request

    await notify_telegram_csat_request(
        chat_id=user.telegram_chat_id,
        ticket_id=ticket.id,
        ticket_title=ticket.title,
        user=user,
    )
    async with async_session_factory() as session:
        fresh = await session.get(Ticket, ticket.id)
        if fresh is None:
            return
        fresh.satisfaction_requested_at = datetime.utcnow()
        session.add(fresh)
        await session.commit()


async def run_once() -> int:
    """Run one pass; returns the number of nudges sent. Never raises."""
    sent = 0
    try:
        pairs = await _due_tickets()
    except Exception:  # noqa: BLE001
        logger.exception("CSAT scheduler: query failed")
        return 0
    for ticket, user in pairs:
        if user is None or not user.telegram_chat_id:
            continue
        try:
            await _send_nudge(ticket, user)
            sent += 1
        except Exception:  # noqa: BLE001
            logger.exception(
                "CSAT scheduler: nudge failed for ticket %s", ticket.id[:8] if ticket.id else "?"
            )
    return sent


async def csat_scheduler_loop() -> None:
    """Run forever: sleep, scan, send."""
    logger.info("CSAT scheduler started (interval=%ds, age>=%dh)", CHECK_INTERVAL_SECONDS, MIN_AGE_HOURS)
    while True:
        try:
            sent = await run_once()
            if sent:
                logger.info("CSAT scheduler: sent %d nudges", sent)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("CSAT scheduler loop iteration failed")
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
