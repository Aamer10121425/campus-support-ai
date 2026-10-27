
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    CheckConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# 1. Role
class Role(Base):
    __tablename__ = "roles"

    role_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    role_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


# 2. Term
class Term(Base):
    __tablename__ = "terms"

    term_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    term_name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


# 3. Requester
class Requester(Base):
    __tablename__ = "requesters"

    requester_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.role_id"), nullable=False
    )
    term_id: Mapped[str | None] = mapped_column(
        ForeignKey("terms.term_id"), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )


# 4. Category
class Category(Base):
    __tablename__ = "categories"

    category_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.role_id"), nullable=True
    )


# 5. PolicyDocument
class PolicyDocument(Base):
    __tablename__ = "policy_documents"

    policy_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(30), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    source_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    owner_role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.role_id"), nullable=True
    )


# 6. KnowledgeArticle
class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"

    article_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), default="published")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_policy_id: Mapped[str | None] = mapped_column(
        ForeignKey("policy_documents.policy_id"), nullable=True
    )


# 7. Ticket
class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    requester_id: Mapped[str] = mapped_column(
        ForeignKey("requesters.requester_id"), nullable=False
    )
    category_id: Mapped[str] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    subject: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open")
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    channel: Mapped[str] = mapped_column(String(30), default="web")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


# 8. Message
class Message(Base):
    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id"), nullable=False
    )
    sender_requester_id: Mapped[str | None] = mapped_column(
        ForeignKey("requesters.requester_id"), nullable=True
    )
    sender_role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.role_id"), nullable=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), default="comment")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    is_internal: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


# 9. Assignment
class Assignment(Base):
    __tablename__ = "assignments"

    assignment_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id"), nullable=False
    )
    assigned_role_id: Mapped[str] = mapped_column(
        ForeignKey("roles.role_id"), nullable=False
    )
    assigned_to_requester_id: Mapped[str | None] = mapped_column(
        ForeignKey("requesters.requester_id"), nullable=True
    )
    assigned_by_requester_id: Mapped[str | None] = mapped_column(
        ForeignKey("requesters.requester_id"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(30), default="active")
    route_reason: Mapped[str] = mapped_column(Text, nullable=False)
    authorized: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# 10. SLA
class SLA(Base):
    __tablename__ = "slas"
    __table_args__ = (
        CheckConstraint("first_response_minutes > 0"),
        CheckConstraint("resolution_minutes > 0"),
        CheckConstraint("escalation_after_minutes > 0"),
    )

    sla_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("categories.category_id"), nullable=True
    )
    priority: Mapped[str] = mapped_column(String(20), nullable=False)
    first_response_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    resolution_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    business_hours_only: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    escalation_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    escalation_role_id: Mapped[str | None] = mapped_column(
        ForeignKey("roles.role_id"), nullable=True
    )


# 11. ResolutionFeedback
class ResolutionFeedback(Base):
    __tablename__ = "resolution_feedback"

    feedback_id: Mapped[str] = mapped_column(String(30), primary_key=True)
    ticket_id: Mapped[str] = mapped_column(
        ForeignKey("tickets.ticket_id"), nullable=False
    )
    requester_id: Mapped[str] = mapped_column(
        ForeignKey("requesters.requester_id"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, nullable=False
    )
