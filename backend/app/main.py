import re

from datetime import date,datetime, timedelta, timezone, time

from fastapi import FastAPI, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import SessionLocal, test_connection
from app.models import (
    Assignment,
    Category,
    KnowledgeArticle,
    Message,
    PolicyDocument,
    Requester,
    Ticket,
    SLA,
)


BUSINESS_START = time(9, 0)
BUSINESS_END = time(17, 0)


def add_business_minutes(start: datetime, minutes: int) -> datetime:
    """Add SLA minutes during weekdays, 09:00–17:00 UTC."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    current = start.astimezone(timezone.utc)
    remaining = minutes

    while remaining > 0:
        # Skip weekends.
        if current.weekday() >= 5:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        opening = current.replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        closing = current.replace(
            hour=17, minute=0, second=0, microsecond=0
        )

        if current < opening:
            current = opening
        elif current >= closing:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        available = int((closing - current).total_seconds() // 60)

        if remaining <= available:
            return current + timedelta(minutes=remaining)

        remaining -= available
        current = (current + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    return current

def business_minutes_between(start: datetime, end: datetime) -> int:
    """Count working minutes between two timestamps, Monday-Friday 09:00-17:00 UTC."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)

    current = start.astimezone(timezone.utc)
    finish = end.astimezone(timezone.utc)

    if finish <= current:
        return 0

    total = 0

    while current < finish:
        if current.weekday() >= 5:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        opening = current.replace(
            hour=9, minute=0, second=0, microsecond=0
        )
        closing = current.replace(
            hour=17, minute=0, second=0, microsecond=0
        )

        if current < opening:
            current = opening
            continue

        if current >= closing:
            current = (current + timedelta(days=1)).replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            continue

        segment_end = min(finish, closing)
        total += max(
            0, int((segment_end - current).total_seconds() // 60)
        )
        current = segment_end

    return total
app = FastAPI(
    title="Campus Support AI",
    description=(
        "Policy-grounded student and faculty support workflow system "
        "with ticket tracking, routing, and operational metrics."
    ),
    version="0.2.0",
)


@app.get("/")
def home():
    return {"message": "Campus Support AI backend is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/db-test")
def database_test():
    try:
        database_name = test_connection()
        return {
            "status": "connected",
            "database": database_name,
        }
    except (SQLAlchemyError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed. Check server status and local configuration.",
        ) from exc


# List tickets, with pagination and optional filters.
@app.get("/tickets")
def list_tickets(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: str | None = None,
    priority: str | None = None,
    category_id: str | None = None,
):
    with SessionLocal() as session:
        query = select(Ticket)

        if status:
            query = query.where(func.lower(Ticket.status) == status.lower())

        if priority:
            query = query.where(func.lower(Ticket.priority) == priority.lower())

        if category_id:
            query = query.where(Ticket.category_id == category_id)

        total = session.scalar(
            select(func.count()).select_from(query.subquery())
        )

        tickets = session.scalars(
            query.order_by(Ticket.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "ticket_id": ticket.ticket_id,
                    "subject": ticket.subject,
                    "status": ticket.status,
                    "priority": ticket.priority,
                    "category_id": ticket.category_id,
                    "requester_id": ticket.requester_id,
                    "created_at": ticket.created_at,
                    "due_at": ticket.due_at,
                }
                for ticket in tickets
            ],
        }


# Retrieve one ticket with its message history and assignments.
@app.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str):
    with SessionLocal() as session:
        ticket = session.get(Ticket, ticket_id)

        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")

        requester = session.get(Requester, ticket.requester_id)
        category = session.get(Category, ticket.category_id)

        messages = session.scalars(
            select(Message)
            .where(Message.ticket_id == ticket_id)
            .order_by(Message.created_at.asc())
        ).all()

        assignments = session.scalars(
            select(Assignment)
            .where(Assignment.ticket_id == ticket_id)
            .order_by(Assignment.assigned_at.asc())
        ).all()

        return {
            "ticket": {
                "ticket_id": ticket.ticket_id,
                "subject": ticket.subject,
                "description": ticket.description,
                "status": ticket.status,
                "priority": ticket.priority,
                "channel": ticket.channel,
                "created_at": ticket.created_at,
                "updated_at": ticket.updated_at,
                "due_at": ticket.due_at,
                "resolution_summary": ticket.resolution_summary,
            },
            "requester": (
                {
                    "requester_id": requester.requester_id,
                    "full_name": requester.full_name,
                    "role_id": requester.role_id,
                    "department": requester.department,
                }
                if requester
                else None
            ),
            "category": (
                {
                    "category_id": category.category_id,
                    "name": category.name,
                }
                if category
                else None
            ),
            "messages": [
                {
                    "message_id": message.message_id,
                    "body": message.body,
                    "message_type": message.message_type,
                    "sender_role_id": message.sender_role_id,
                    "created_at": message.created_at,
                    "is_internal": message.is_internal,
                }
                for message in messages
            ],
            "assignments": [
                {
                    "assignment_id": assignment.assignment_id,
                    "assigned_role_id": assignment.assigned_role_id,
                    "assigned_to_requester_id": (
                        assignment.assigned_to_requester_id
                    ),
                    "status": assignment.status,
                    "route_reason": assignment.route_reason,
                    "authorized": assignment.authorized,
                    "assigned_at": assignment.assigned_at,
                    "due_at": assignment.due_at,
                }
                for assignment in assignments
            ],
        }


# Search knowledge articles. Expired or non-published articles are
# excluded by default to avoid using stale material as current guidance.
@app.get("/articles")
def list_articles(
    search: str | None = None,
    category_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    include_inactive: bool = False,
):
    with SessionLocal() as session:
        query = select(KnowledgeArticle)

        if not include_inactive:
            query = query.where(
                func.lower(KnowledgeArticle.status) == "published"
            )
            query = query.where(
                or_(
                    KnowledgeArticle.expires_at.is_(None),
                    KnowledgeArticle.expires_at >= date.today(),
                )
            )

        if search:
            term = f"%{search.strip()}%"
            query = query.where(
                or_(
                    KnowledgeArticle.title.ilike(term),
                    KnowledgeArticle.content.ilike(term),
                )
            )

        if category_id:
            query = query.where(
                KnowledgeArticle.category_id == category_id
            )

        total = session.scalar(
            select(func.count()).select_from(query.subquery())
        )

        articles = session.scalars(
            query.order_by(KnowledgeArticle.title.asc())
            .offset(offset)
            .limit(limit)
        ).all()

        return {
            "total": total or 0,
            "limit": limit,
            "offset": offset,
            "items": [
                {
                    "article_id": article.article_id,
                    "title": article.title,
                    "category_id": article.category_id,
                    "status": article.status,
                    "expires_at": article.expires_at,
                    "source_policy_id": article.source_policy_id,
                }
                for article in articles
            ],
        }


# Retrieve an article and the policy document it references.
@app.get("/articles/{article_id}")
def get_article(article_id: str):
    with SessionLocal() as session:
        article = session.get(KnowledgeArticle, article_id)

        if article is None:
            raise HTTPException(status_code=404, detail="Article not found")

        policy = (
            session.get(PolicyDocument, article.source_policy_id)
            if article.source_policy_id
            else None
        )

        expired = (
            article.status.lower() != "published"
            or (
                article.expires_at is not None
                and article.expires_at < date.today()
            )
        )

        return {
            "article": {
                "article_id": article.article_id,
                "title": article.title,
                "content": article.content,
                "category_id": article.category_id,
                "status": article.status,
                "created_at": article.created_at,
                "updated_at": article.updated_at,
                "expires_at": article.expires_at,
                "is_unavailable_for_current_guidance": expired,
            },
            "source_policy": (
                {
                    "policy_id": policy.policy_id,
                    "title": policy.title,
                    "version": policy.version,
                    "status": policy.status,
                    "effective_from": policy.effective_from,
                    "expires_at": policy.expires_at,
                    "source_uri": policy.source_uri,
                }
                if policy
                else None
            ),
            "citation_warning": (
                "This article is expired or not published. "
                "Do not use it as current policy guidance."
                if expired
                else None
            ),
        }


# Basic operational metrics for the dashboard.
@app.get("/stats")
def get_stats():
    with SessionLocal() as session:
        total_tickets = session.scalar(
            select(func.count()).select_from(Ticket)
        ) or 0

        status_rows = session.execute(
            select(Ticket.status, func.count())
            .group_by(Ticket.status)
        ).all()

        priority_rows = session.execute(
            select(Ticket.priority, func.count())
            .group_by(Ticket.priority)
        ).all()

        unauthorized_assignments = session.scalar(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.authorized.is_(False))
        ) or 0

        expired_articles = session.scalar(
            select(func.count())
            .select_from(KnowledgeArticle)
            .where(
                or_(
                    func.lower(KnowledgeArticle.status) != "published",
                    KnowledgeArticle.expires_at < date.today(),
                )
            )
        ) or 0

        overdue_open_tickets = session.scalar(
            select(func.count())
            .select_from(Ticket)
            .where(
                func.lower(Ticket.status).in_(["open", "in_progress"]),
                Ticket.due_at.is_not(None),
                Ticket.due_at < func.now(),
            )
        ) or 0

        return {
            "total_tickets": total_tickets,
            "tickets_by_status": {
                str(status): count for status, count in status_rows
            },
            "tickets_by_priority": {
                str(priority): count for priority, count in priority_rows
            },
            "unauthorized_assignments": unauthorized_assignments,
            "expired_or_unpublished_articles": expired_articles,
            "overdue_open_tickets": overdue_open_tickets,
        }

@app.get("/audit")
def audit_business_rules():
    """
    Inspect policy citations, routing authorization, unsupported responses,
    overdue tickets, and possible missed escalations.
    Findings are diagnostic and do not modify database records.
    """
    today = date.today()
    now = datetime.now(timezone.utc)
    findings = []

    with SessionLocal() as session:
        # Load records once for a consistent audit pass.
        articles = session.scalars(select(KnowledgeArticle)).all()
        article_by_id = {a.article_id: a for a in articles}
        messages = session.scalars(select(Message)).all()
        tickets = session.scalars(select(Ticket)).all()
        assignments = session.scalars(select(Assignment)).all()
        slas = session.scalars(select(SLA)).all()

        assignments_by_ticket = {}
        for assignment in assignments:
            assignments_by_ticket.setdefault(
                assignment.ticket_id, []
            ).append(assignment)

        # Rule 1: A message cites an expired or unpublished article.
        citation_pattern = re.compile(
            r"\[CITATION:\s*([A-Za-z0-9_-]+)\s*\]",
            re.IGNORECASE,
        )

        for message in messages:
            for match in citation_pattern.finditer(message.body):
                article_id = match.group(1)
                article = article_by_id.get(article_id)

                if article is None:
                    findings.append({
                        "rule": "citation_integrity",
                        "severity": "high",
                        "record_id": message.message_id,
                        "ticket_id": message.ticket_id,
                        "details": (
                            f"Citation references unknown article {article_id}."
                        ),
                    })
                    continue

                is_expired = (
                    article.status.lower() != "published"
                    or (
                        article.expires_at is not None
                        and article.expires_at < today
                    )
                )

                if is_expired:
                    findings.append({
                        "rule": "expired_citation",
                        "severity": "high",
                        "record_id": message.message_id,
                        "ticket_id": message.ticket_id,
                        "article_id": article_id,
                        "details": (
                            "A response cites an expired or unpublished article."
                        ),
                    })

        # Rule 2: An assignment is explicitly marked unauthorized.
        for assignment in assignments:
            if not assignment.authorized:
                findings.append({
                    "rule": "unauthorized_routing",
                    "severity": "high",
                    "record_id": assignment.assignment_id,
                    "ticket_id": assignment.ticket_id,
                    "details": assignment.route_reason,
                })

        # Rule 3: A response explicitly admits that no policy source was checked.
        for message in messages:
            body = message.body.lower()

            if (
                message.message_type.lower() == "answer"
                and (
                    "no policy source was checked" in body
                    or "no policy source was used" in body
                )
            ):
                findings.append({
                    "rule": "unsupported_response",
                    "severity": "high",
                    "record_id": message.message_id,
                    "ticket_id": message.ticket_id,
                    "details": (
                        "The answer explicitly says no policy source was checked."
                    ),
                })

                # Rule 4: Validate stored deadlines against business-hours SLAs.
        slas_by_key = {}
        for sla in slas:
            slas_by_key.setdefault(
                (sla.category_id, sla.priority.lower()), []
            ).append(sla)

        for ticket in tickets:
            matching_slas = (
                slas_by_key.get(
                    (ticket.category_id, ticket.priority.lower()), []
                )
                + slas_by_key.get((None, ticket.priority.lower()), [])
            )

            if ticket.due_at is not None:
                stored_due = ticket.due_at
                if stored_due.tzinfo is None:
                    stored_due = stored_due.replace(tzinfo=timezone.utc)

                if (
                    ticket.status.lower() in {"open", "in_progress"}
                    and stored_due < now
                ):
                    findings.append({
                        "rule": "overdue_ticket",
                        "severity": (
                            "high"
                            if ticket.priority.lower() == "high"
                            else "medium"
                        ),
                        "record_id": ticket.ticket_id,
                        "ticket_id": ticket.ticket_id,
                        "details": (
                            "Ticket is open/in progress and its stored deadline "
                            "has passed."
                        ),
                    })

            business_slas = [
                sla for sla in matching_slas
                if sla.business_hours_only
            ]

            if ticket.due_at is None or not business_slas:
                continue

            # Use the shortest matching resolution SLA.
            sla = min(
                business_slas,
                key=lambda item: item.resolution_minutes,
            )

            expected_due = add_business_minutes(
                ticket.created_at,
                sla.resolution_minutes,
            )

            stored_due = ticket.due_at
            if stored_due.tzinfo is None:
                stored_due = stored_due.replace(tzinfo=timezone.utc)

            if abs((stored_due - expected_due).total_seconds()) > 60:
                findings.append({
                    "rule": "business_hours_sla_issue",
                    "severity": "high",
                    "record_id": ticket.ticket_id,
                    "ticket_id": ticket.ticket_id,
                    "details": (
                        f"Stored deadline {stored_due.isoformat()} does not "
                        f"match the business-hours deadline "
                        f"{expected_due.isoformat()}."
                    ),
                })

                # Rule 5: Check escalation thresholds for active tickets only.
        for ticket in tickets:
            if (
                ticket.priority.lower() != "high"
                or ticket.status.lower() not in {"open", "in_progress"}
            ):
                continue

            matching_slas = (
                slas_by_key.get((ticket.category_id, "high"), [])
                + slas_by_key.get((None, "high"), [])
            )

            if not matching_slas:
                continue

            threshold = min(
                sla.escalation_after_minutes
                for sla in matching_slas
            )

            business_elapsed = business_minutes_between(
                ticket.created_at,
                now,
            )

            if business_elapsed < threshold:
                continue

            ticket_assignments = assignments_by_ticket.get(
                ticket.ticket_id, []
            )

            escalation_roles = {
                sla.escalation_role_id
                for sla in matching_slas
                if sla.escalation_role_id is not None
            }

            escalation_exists = any(
                "escalat" in (assignment.route_reason or "").lower()
                or assignment.assigned_role_id in escalation_roles
                for assignment in ticket_assignments
            )

            if not escalation_exists:
                findings.append({
                    "rule": "possible_missed_escalation",
                    "severity": "high",
                    "record_id": ticket.ticket_id,
                    "ticket_id": ticket.ticket_id,
                    "details": (
                        f"Active high-priority ticket exceeded the "
                        f"{threshold}-business-minute escalation threshold "
                        f"without a matching escalation assignment. "
                        f"Business minutes elapsed: {business_elapsed}."
                    ),
                })

    
    counts = {}
    severity_counts = {}

    for finding in findings:
        rule = finding["rule"]
        severity = finding.get("severity", "unknown")

        counts[rule] = counts.get(rule, 0) + 1
        severity_counts[severity] = (
            severity_counts.get(severity, 0) + 1
        )

    # Limit detailed findings independently for each rule.
    max_per_rule = 500
    returned_findings = []
    returned_by_rule = {}

    for finding in findings:
        rule = finding["rule"]
        returned_count = returned_by_rule.get(rule, 0)

        if returned_count < max_per_rule:
            returned_findings.append(finding)
            returned_by_rule[rule] = returned_count + 1

    returned_counts = {
        rule: returned_by_rule.get(rule, 0)
        for rule in counts
    }

    omitted_counts = {
        rule: counts[rule] - returned_counts[rule]
        for rule in counts
    }

    return {
        "audit_status": "completed",
        "records_scanned": {
            "tickets": len(tickets),
            "messages": len(messages),
            "assignments": len(assignments),
            "articles": len(articles),
        },
        "finding_count": len(findings),
        "findings_by_rule": counts,
        "findings_by_severity": severity_counts,
        "returned_findings_by_rule": returned_counts,
        "omitted_findings_by_rule": omitted_counts,
        "findings": returned_findings,
        "truncated": any(
            omitted > 0 for omitted in omitted_counts.values()
        ),
        "notes": [
            "Findings are diagnostic; no database records were changed.",
            "Overdue checks use stored due times and do not apply business calendars.",
            "Escalation thresholds are evaluated using business minutes.",
            "A missing escalation match is a potential issue, not definitive proof.",
            "Detailed findings are limited to 500 per rule; total counts include omitted findings.",
        ],
    }
