
import json
import random
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from sqlalchemy import delete

from app.db import engine, SessionLocal
from app.models import (
    Base,
    Role,
    Term,
    Requester,
    Category,
    PolicyDocument,
    KnowledgeArticle,
    Ticket,
    Message,
    Assignment,
    SLA,
    ResolutionFeedback,
)

SEED = 20261022
ANCHOR = datetime(2026, 10, 26, 12, 0, tzinfo=timezone.utc)
OUTPUT_DIR = Path("generated")

random.seed(SEED)


def dt(days_ago=0, hours=0):
    return ANCHOR - timedelta(days=days_ago, hours=hours)


def build_dataset():
    rng = random.Random(SEED)
    truth = {
        "seed": SEED,
        "anchor_date": ANCHOR.isoformat(),
        "expected_counts": {
            "roles": 7,
            "terms": 3,
            "requesters": 1000,
            "categories": 8,
            "policy_documents": 20,
            "knowledge_articles": 200,
            "tickets": 5000,
            "messages": 20000,
            "assignments": 5000,
            "slas": 24,
            "resolution_feedback": 1000,
        },
        "anomalies": [],
    }

    roles = [
        ("ROLE-STUDENT", "Student"),
        ("ROLE-FACULTY", "Faculty"),
        ("ROLE-SUPPORT", "Support Agent"),
        ("ROLE-REGISTRAR", "Registrar"),
        ("ROLE-FINANCE", "Finance Officer"),
        ("ROLE-IT", "IT Administrator"),
        ("ROLE-MANAGER", "Support Manager"),
    ]

    terms = [
        ("TERM-2026-SPRING", "Spring 2026", date(2026, 1, 1), date(2026, 5, 31)),
        ("TERM-2026-FALL", "Fall 2026", date(2026, 8, 1), date(2026, 12, 31)),
        ("TERM-2027-SPRING", "Spring 2027", date(2027, 1, 1), date(2027, 5, 31)),
    ]

    category_names = [
        ("CAT-IT", "IT Support", "Technical problems and account access", "ROLE-IT"),
        ("CAT-REG", "Registration", "Enrollment and registration questions", "ROLE-REGISTRAR"),
        ("CAT-FIN", "Finance", "Fees, refunds, and payments", "ROLE-FINANCE"),
        ("CAT-ATT", "Attendance", "Attendance records and corrections", "ROLE-FACULTY"),
        ("CAT-EXAM", "Examinations", "Exam schedules and examination rules", "ROLE-REGISTRAR"),
        ("CAT-LMS", "Learning Platform", "Learning platform and course access", "ROLE-IT"),
        ("CAT-LIB", "Library", "Library services and borrowing", "ROLE-SUPPORT"),
        ("CAT-GEN", "General Inquiry", "General campus questions", "ROLE-SUPPORT"),
    ]

    first_names = [
        "Aarav", "Aisha", "Arjun", "Fatima", "Ibrahim", "Maya",
        "Noah", "Sara", "Zara", "Rohan", "Anaya", "Omar",
    ]
    last_names = [
        "Khan", "Patel", "Sharma", "Reddy", "Ali", "Thomas",
        "Joseph", "Singh", "Das", "Rao", "Mehta", "Ahmed",
    ]

    requesters = []
    for i in range(1, 1001):
        role_id = "ROLE-STUDENT" if i <= 800 else "ROLE-FACULTY"
        requesters.append({
            "requester_id": f"REQ-{i:05d}",
            "full_name": f"{rng.choice(first_names)} {rng.choice(last_names)}",
            "email": f"requester{i:05d}@example.edu",
            "role_id": role_id,
            "term_id": "TERM-2026-FALL" if role_id == "ROLE-STUDENT" else None,
            "department": rng.choice([
                "Computer Science", "Engineering", "Business",
                "Arts and Sciences", "Administration",
            ]),
            "created_at": dt(rng.randint(30, 900)),
        })

    policies = []
    for i in range(1, 21):
        expired = i in (1, 2)
        policies.append({
            "policy_id": f"POL-{i:04d}",
            "title": f"Campus Policy {i:03d}",
            "version": "1.0",
            "effective_from": date(2025, 1, 1),
            "expires_at": date(2026, 10, 1) if expired else date(2027, 12, 31),
            "status": "expired" if expired else "active",
            "source_uri": f"https://example.edu/policies/{i:04d}",
            "content": (
                f"Synthetic policy {i}. This is generated test content, "
                "not an official campus policy. Verify applicable rules "
                "against an approved source before answering a real request."
            ),
            "owner_role_id": rng.choice([r[0] for r in roles[2:]]),
        })

    articles = []
    for i in range(1, 201):
        category = category_names[(i - 1) % len(category_names)]
        expired = i == 1
        policy_number = 1 if i == 1 else ((i - 1) % 20) + 1
        articles.append({
            "article_id": f"ART-{i:04d}",
            "title": f"{category[1]} Help Article {i:03d}",
            "content": (
                f"Synthetic knowledge article {i} about {category[1].lower()}. "
                "This sample content is for testing retrieval and citation "
                "validation only; it is not an authoritative campus policy."
            ),
            "category_id": category[0],
            "status": "expired" if expired else "published",
            "created_at": dt(rng.randint(10, 300)),
            "updated_at": dt(rng.randint(1, 9)),
            "reviewed_at": dt(rng.randint(1, 30)),
            "expires_at": date(2026, 10, 1) if expired else date(2027, 10, 1),
            "source_policy_id": f"POL-{policy_number:04d}",
        })

    priorities = ["low", "normal", "high"]
    slas = []
    sla_lookup = {}
    for category in category_names:
        for priority in priorities:
            sla_id = f"SLA-{category[0]}-{priority.upper()}"
            minutes = {"low": 1440, "normal": 480, "high": 120}[priority]
            escalation = {"low": 720, "normal": 240, "high": 60}[priority]
            slas.append({
                "sla_id": sla_id,
                "category_id": category[0],
                "priority": priority,
                "first_response_minutes": max(30, minutes // 4),
                "resolution_minutes": minutes,
                "business_hours_only": True,
                "escalation_after_minutes": escalation,
                "escalation_role_id": "ROLE-MANAGER",
            })
            sla_lookup[(category[0], priority)] = slas[-1]

    tickets = []
    messages = []
    assignments = []
    feedback = []

    for i in range(1, 5001):
        ticket_id = f"TKT-{i:06d}"
        requester = requesters[rng.randrange(len(requesters))]
        category = category_names[rng.randrange(len(category_names))]
        priority = rng.choice(priorities)

        created_at = dt(
            rng.randint(0, 100),
            hours=rng.randint(0, 12),
        )

        # Plant a known business-hours SLA anomaly.
        if i == 4:
            created_at = datetime(2026, 10, 25, 22, 0, tzinfo=timezone.utc)
            category = category_names[0]
            priority = "high"

        # Make the missed-escalation case old enough to exceed its SLA.
        if i == 5:
            created_at = dt(3)
            category = category_names[0]
            priority = "high"

        sla = sla_lookup[(category[0], priority)]
        due_at = created_at + timedelta(minutes=sla["resolution_minutes"])

        if i == 4:
            # Deliberately wrong: ignores business hours.
            due_at = created_at + timedelta(minutes=120)

        status = rng.choice(["open", "in_progress", "resolved", "closed"])
        if i in (1, 2, 3, 4, 5):
            status = "in_progress"

        tickets.append({
            "ticket_id": ticket_id,
            "requester_id": requester["requester_id"],
            "category_id": category[0],
            "subject": f"{category[1]} request {i:06d}",
            "description": (
                f"Synthetic ticket {i} for {category[1].lower()}. "
                "This request is generated test data."
            ),
            "status": status,
            "priority": priority,
            "channel": rng.choice(["web", "email", "mobile"]),
            "created_at": created_at,
            "updated_at": created_at + timedelta(minutes=rng.randint(1, 60)),
            "due_at": due_at,
            "resolution_summary": (
                "Synthetic resolution summary."
                if status in ("resolved", "closed") else None
            ),
        })

        # Normal routing is based on the category's default role.
        assigned_role = category[3]
        authorized = True
        route_reason = f"Category {category[1]} default routing"

        if i == 2:
            # Deliberately unauthorized route for validation.
            assigned_role = "ROLE-FINANCE" if category[0] == "CAT-IT" else "ROLE-IT"
            authorized = False
            route_reason = "Injected unauthorized routing anomaly"
            truth["anomalies"].append({
                "type": "unauthorized_route",
                "ticket_id": ticket_id,
                "assignment_id": f"ASN-{i:06d}",
                "expected": "Assignment should be rejected or escalated for review",
            })

        assignments.append({
            "assignment_id": f"ASN-{i:06d}",
            "ticket_id": ticket_id,
            "assigned_role_id": assigned_role,
            "assigned_to_requester_id": None,
            "assigned_by_requester_id": None,
            "assigned_at": created_at + timedelta(minutes=5),
            "due_at": due_at,
            "status": "active" if status in ("open", "in_progress") else "completed",
            "route_reason": route_reason,
            "authorized": authorized,
        })

        # Exactly four messages per ticket => 20,000 total.
        messages.append({
            "message_id": f"MSG-{(i - 1) * 4 + 1:07d}",
            "ticket_id": ticket_id,
            "sender_requester_id": requester["requester_id"],
            "sender_role_id": None,
            "body": tickets[-1]["description"],
            "message_type": "request",
            "created_at": created_at,
            "is_internal": False,
        })
        messages.append({
            "message_id": f"MSG-{(i - 1) * 4 + 2:07d}",
            "ticket_id": ticket_id,
            "sender_requester_id": None,
            "sender_role_id": "ROLE-SUPPORT",
            "body": "Your request has been received and routed for review.",
            "message_type": "response",
            "created_at": created_at + timedelta(minutes=5),
            "is_internal": False,
        })
        messages.append({
            "message_id": f"MSG-{(i - 1) * 4 + 3:07d}",
            "ticket_id": ticket_id,
            "sender_requester_id": requester["requester_id"],
            "sender_role_id": None,
            "body": "Thank you. Please let me know the applicable next steps.",
            "message_type": "comment",
            "created_at": created_at + timedelta(minutes=10),
            "is_internal": False,
        })

        if i == 1:
            answer = (
                "Please consult the applicable procedure. "
                "[CITATION: ART-0001]"
            )
            truth["anomalies"].append({
                "type": "expired_citation",
                "ticket_id": ticket_id,
                "article_id": "ART-0001",
                "expected": "The cited article is expired and must not support the answer",
            })
        elif i == 3:
            answer = (
                "Your request is approved. No policy source was checked "
                "for this generated response."
            )
            truth["anomalies"].append({
                "type": "unsupported_response",
                "ticket_id": ticket_id,
                "message_id": f"MSG-{(i - 1) * 4 + 4:07d}",
                "expected": "Response requires verifiable policy evidence",
            })
        else:
            article_number = rng.randint(2, 200)
            answer = (
                "This is a synthetic response for testing. "
                f"[CITATION: ART-{article_number:04d}]"
            )

        messages.append({
            "message_id": f"MSG-{(i - 1) * 4 + 4:07d}",
            "ticket_id": ticket_id,
            "sender_requester_id": None,
            "sender_role_id": "ROLE-SUPPORT",
            "body": answer,
            "message_type": "answer",
            "created_at": created_at + timedelta(minutes=15),
            "is_internal": False,
        })

        if i == 4:
            truth["anomalies"].append({
                "type": "business_hours_sla_issue",
                "ticket_id": ticket_id,
                "expected": (
                    "SLA due time must account for business hours; "
                    "the injected due time is a simple elapsed-time calculation"
                ),
            })

        if i == 5:
            truth["anomalies"].append({
                "type": "missed_escalation",
                "ticket_id": ticket_id,
                "expected": (
                    "High-priority ticket exceeds escalation threshold "
                    "but has no escalation assignment"
                ),
            })

        if i <= 1000:
            feedback.append({
                "feedback_id": f"FDB-{i:06d}",
                "ticket_id": ticket_id,
                "requester_id": requester["requester_id"],
                "rating": rng.randint(1, 5),
                "feedback_text": rng.choice([
                    "Helpful response.",
                    "Needs more detail.",
                    "Issue resolved.",
                    "Response was delayed.",
                    "Clear instructions.",
                ]),
                "resolution_accepted": rng.choice([True, False]),
                "created_at": created_at + timedelta(hours=2),
            })

    return truth, roles, terms, requesters, category_names, policies, articles, tickets, messages, assignments, slas, feedback


def main():
    database_name = engine.url.database
    if database_name != "campus_support_ai":
        raise RuntimeError(
            f"Refusing to seed unexpected database: {database_name!r}"
        )

    (
        truth, roles, terms, requesters, category_names, policies, articles,
        tickets, messages, assignments, slas, feedback
    ) = build_dataset()

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Save the separate ground-truth file before loading the database.
    (OUTPUT_DIR / "ground_truth.json").write_text(
        json.dumps(truth, indent=2),
        encoding="utf-8",
    )

    # Delete in foreign-key-safe order so the generator is reproducible.
    delete_order = [
        ResolutionFeedback, Message, Assignment, Ticket,
        KnowledgeArticle, PolicyDocument, SLA, Requester,
        Category, Term, Role,
    ]

    with SessionLocal() as session:
        try:
            for model in delete_order:
                session.execute(delete(model))
            session.flush()

            session.add_all([
                Role(role_id=r[0], role_name=r[1], description=f"Synthetic role: {r[1]}")
                for r in roles
            ])
            session.add_all([
                Term(
                    term_id=t[0], term_name=t[1],
                    start_date=t[2], end_date=t[3],
                    is_active=(t[0] == "TERM-2026-FALL"),
                )
                for t in terms
            ])
            session.flush()

            session.add_all([
                Category(
                    category_id=c[0], name=c[1],
                    description=c[2], default_role_id=c[3],
                )
                for c in category_names
            ])
            session.flush()

            session.add_all([Requester(**r) for r in requesters])
            session.add_all([PolicyDocument(**p) for p in policies])
            session.flush()

            session.add_all([KnowledgeArticle(**a) for a in articles])
            session.add_all([SLA(**s) for s in slas])
            session.flush()

            # Insert and save tickets before their dependent records.
            session.add_all([Ticket(**t) for t in tickets])
            session.flush()

            session.add_all([Assignment(**a) for a in assignments])
            session.add_all([Message(**m) for m in messages])
            session.flush()

            session.add_all([
                ResolutionFeedback(**f) for f in feedback
            ])

            session.commit()

        except Exception:
            session.rollback()
            raise


    print("Synthetic data generated successfully.")
    print(f"Seed: {SEED}")
    print(f"Ground truth: {OUTPUT_DIR / 'ground_truth.json'}")
    for name, expected in truth["expected_counts"].items():
        print(f"{name}: {expected}")
    print(f"Known anomalies planted: {len(truth['anomalies'])}")


if __name__ == "__main__":
    main()
