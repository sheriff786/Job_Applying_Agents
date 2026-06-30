"""Database models and connection setup."""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    String,
    Text,
    Boolean,
    Integer,
    ForeignKey,
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from src.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Job(Base):
    """Normalized job listing from any source."""

    __tablename__ = "jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False)  # greenhouse, lever, ashby, remoteok, linkedin
    external_id = Column(String(255), unique=True, nullable=False)
    company = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    description_raw = Column(Text, nullable=False)
    location = Column(String(255))
    remote = Column(Boolean, default=False)
    seniority_level = Column(String(50))
    posted_at = Column(DateTime)
    url = Column(Text)
    salary_min = Column(Integer)
    salary_max = Column(Integer)
    currency = Column(String(10))

    # Parsed fields (filled by JD parser)
    skills = Column(ARRAY(String), default=[])
    tech_stack = Column(ARRAY(String), default=[])
    parsed_data = Column(JSONB, default={})

    # Embedding
    embedding = Column(Text)  # stored as pgvector via raw SQL

    # Scoring
    fit_score = Column(Float)
    fit_reasoning = Column(Text)

    # Status
    status = Column(
        String(50), default="new"
    )  # new, scored, tailored, pending_review, applied, rejected, interview
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    applications = relationship("Application", back_populates="job")


class Application(Base):
    """Tracks each application submitted."""

    __tablename__ = "applications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    resume_version = Column(String(255))
    resume_path = Column(Text)
    cover_letter = Column(Text)
    status = Column(
        String(50), default="pending_review"
    )  # pending_review, approved, submitted, rejected, interview, offer
    submitted_at = Column(DateTime)
    submission_method = Column(String(50))  # api, manual
    response_received = Column(Boolean, default=False)
    response_date = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship("Job", back_populates="applications")


class ResumeVersion(Base):
    """Tracks generated resume versions."""

    __tablename__ = "resume_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False)
    file_path = Column(Text, nullable=False)
    changes_summary = Column(Text)
    keywords_matched = Column(ARRAY(String), default=[])
    score_before = Column(Float)
    score_after = Column(Float)
    approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
