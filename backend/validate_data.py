
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import (
    Assignment,
    KnowledgeArticle,
    Message,
    PolicyDocument,
    Requester,
    ResolutionFeedback,
    Role,
    SLA,
    Term,
    Ticket,
)


EXPECTED_COUNTS = {
    Role: 7,
    Term: 3,
    Requester: 1000,
    PolicyDocument: 20,
    KnowledgeArticle: 200,
    Ticket: 5000,
    Message: 20000,
    Assignment: 5000,
    SLA: 24,
    ResolutionFeedback: 1000,
}


def add_business_minutes(start: datetime, minutes: int) -> datetime:
    """Add minutes during weekdays, 09:00-17:00 UTC."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)

    current = start.astimezone(timezone.utc)
    remaining = minutes

    while remaining > 0:
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

        available = int(
            (closing - current).total_seconds() // 60
        )

        if remaining <= available:
            return current + timedelta(minutes=remaining)

        remaining -= available
        current = (current + timedelta(days=1)).replace(
            hour=9, minute=0, second=0, microsecond=0
        )

    return current


def count_records(session, model):
    return session.scalar(
        select(func.count()).select_from(model)
    )


def main():
    errors = []
    warnings = []

    truth_path = (
        Path(__file__).parent
        / "generated"
        / "ground_truth.json"
    )

    if not truth_path.exists():
        raise SystemExit(
            f"Ground-truth file not found: {truth_path}"
        )

    with truth_path.open("r", encoding="utf-8") as file:
        ground_truth = json.load(file)

    anomalies = {
        item["type"]: item
        for item in ground_truth["anomalies"]
    }

    with SessionLocal() as session:
        print("\n=== CAMPUS SUPPORT AI DATA VALIDATION ===\n")

        # 1. Validate expected record counts.
        for model, expected in EXPECTED_COUNTS.items():
            actual = count_records(session, model)
            status = "PASS" if actual == expected else "FAIL"

            print(
                f"[{status}] {model.__tablename__}: "
                f"expected={expected}, actual={actual}"
            )

            if actual != expected:
                errors.append(
                    f"{model.__tablename__}: "
                    f"expected {expected}, got {actual}"
                )

        # 2. Check tickets with missing requesters.
        orphan_tickets = session.scalar(
            select(func.count())
            .select_from(Ticket)
            .outerjoin(
                Requester,
                Ticket.requester_id == Requester.requester_id,
            )
            .where(Requester.requester_id.is_(None))
        )

        print(f"\nTickets with missing requesters: {orphan_tickets}")

        if orphan_tickets:
            errors.append("Tickets reference missing requesters.")

        # 3. Check assignments with missing tickets.
        orphan_assignments = session.scalar(
            select(func.count())
            .select_from(Assignment)
            .outerjoin(
                Ticket,
                Assignment.ticket_id == Ticket.ticket_id,
            )
            .where(Ticket.ticket_id.is_(None))
        )

        print(
            f"Assignments with missing tickets: "
            f"{orphan_assignments}"
        )

        if orphan_assignments:
            errors.append("Assignments reference missing tickets.")

        # 4. Check messages with missing tickets.
        orphan_messages = session.scalar(
            select(func.count())
            .select_from(Message)
            .outerjoin(
                Ticket,
                Message.ticket_id == Ticket.ticket_id,
            )
            .where(Ticket.ticket_id.is_(None))
        )

        print(f"Messages with missing tickets: {orphan_messages}")

        if orphan_messages:
            errors.append("Messages reference missing tickets.")

        # 5. Detect the planted expired-article citation.
        expired_case = anomalies["expired_citation"]

        expired_article = session.get(
            KnowledgeArticle,
            expired_case["article_id"],
        )

        expired_messages = session.scalars(
            select(Message).where(
                Message.ticket_id == expired_case["ticket_id"]
            )
        ).all()

        citation_found = any(
            expired_case["article_id"] in (message.body or "")
            for message in expired_messages
        )

        article_is_expired = (
            expired_article is not None
            and (
                (expired_article.status or "").lower() == "expired"
                or (
                    expired_article.expires_at is not None
                    and expired_article.expires_at < date.today()
                )
            )
        )

        expired_detected = citation_found and article_is_expired

        print(
            f"\nExpired citation anomaly detected: "
            f"{expired_detected}"
        )

        if expired_detected:
            warnings.append(
                "Expired article cited by a ticket message."
            )
        else:
            errors.append(
                "Could not confirm the planted expired citation."
            )

        # 6. Detect the planted unauthorized assignment.
        route_case = anomalies["unauthorized_route"]

        route_assignment = session.get(
            Assignment,
            route_case["assignment_id"],
        )

        unauthorized_detected = (
            route_assignment is not None
            and route_assignment.ticket_id == route_case["ticket_id"]
            and route_assignment.authorized is False
        )

        print(
            f"Unauthorized route anomaly detected: "
            f"{unauthorized_detected}"
        )

        if unauthorized_detected:
            warnings.append("Unauthorized routing detected.")
        else:
            errors.append(
                "Could not confirm the planted unauthorized route."
            )

        # 7. Detect the planted unsupported response.
        unsupported_case = anomalies["unsupported_response"]

        unsupported_message = session.get(
            Message,
            unsupported_case["message_id"],
        )

        unsupported_detected = (
            unsupported_message is not None
            and unsupported_message.ticket_id
            == unsupported_case["ticket_id"]
            and "no policy source was checked"
            in (unsupported_message.body or "").lower()
        )

        print(
            f"Unsupported response anomaly detected: "
            f"{unsupported_detected}"
        )

        if unsupported_detected:
            warnings.append(
                "Response explicitly states that no policy source "
                "was checked."
            )
        else:
            errors.append(
                "Could not confirm the planted unsupported response."
            )

        # 8. Verify the planted business-hours SLA anomaly.
        business_case = anomalies["business_hours_sla_issue"]

        business_ticket = session.get(
            Ticket,
            business_case["ticket_id"],
        )

        business_detected = False

        if business_ticket is not None and business_ticket.due_at is not None:
            matching_sla = session.scalars(
                select(SLA).where(
                    SLA.category_id == business_ticket.category_id,
                    SLA.priority == business_ticket.priority,
                    SLA.business_hours_only.is_(True),
                )
            ).first()

            if matching_sla is not None:
                expected_due = add_business_minutes(
                    business_ticket.created_at,
                    matching_sla.resolution_minutes,
                )

                stored_due = business_ticket.due_at
                if stored_due.tzinfo is None:
                    stored_due = stored_due.replace(
                        tzinfo=timezone.utc
                    )
                else:
                    stored_due = stored_due.astimezone(timezone.utc)

                business_detected = (
                    abs(
                        (stored_due - expected_due).total_seconds()
                    ) > 60
                )

                print(
                    f"Stored SLA deadline: {stored_due.isoformat()}"
                )
                print(
                    f"Expected business-hours deadline: "
                    f"{expected_due.isoformat()}"
                )

        print(
            f"Business-hours SLA violation confirmed: "
            f"{business_detected}"
        )

        if business_detected:
            warnings.append(
                "Confirmed planted business-hours SLA violation."
            )
        else:
            errors.append(
                "Could not confirm the planted business-hours SLA violation."
            )


        # 9. Inspect the planted missed-escalation case.
        escalation_case = anomalies["missed_escalation"]

        escalation_ticket = session.get(
            Ticket,
            escalation_case["ticket_id"],
        )

        escalation_assignments = session.scalars(
            select(Assignment).where(
                Assignment.ticket_id
                == escalation_case["ticket_id"]
            )
        ).all()

        has_escalation_assignment = any(
            "escalat" in (
                assignment.route_reason or ""
            ).lower()
            or assignment.assigned_role_id == "ROLE-MANAGER"
            for assignment in escalation_assignments
        )

        escalation_detected = (
            escalation_ticket is not None
            and escalation_ticket.priority.lower() == "high"
            and not has_escalation_assignment
        )

        print(
            f"Missed escalation anomaly detected: "
            f"{escalation_detected}"
        )

        if escalation_detected:
            warnings.append(
                "Potential missed escalation detected. "
                "Confirm the SLA threshold and elapsed time."
            )
        else:
            warnings.append(
                "Missed escalation not conclusively verified. "
                "Check the ticket priority, SLA threshold, and "
                "assignment history."
            )

    print("\n=== VALIDATION SUMMARY ===")
    print(f"Structural errors: {len(errors)}")
    print(f"Warnings / anomaly findings: {len(warnings)}")

    for item in errors:
        print(f"[ERROR] {item}")

    for item in warnings:
        print(f"[WARNING] {item}")

    if errors:
        print("\nValidation FAILED.")
        raise SystemExit(1)

    print(
        "\nStructural validation passed. "
        "Review warnings before declaring all business rules validated."
    )


if __name__ == "__main__":
    main()
