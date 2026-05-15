from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    preferences = relationship("StudentPreference", back_populates="student", cascade="all, delete-orphan")


class StudentPreference(Base):
    __tablename__ = "student_preferences"
    __table_args__ = (UniqueConstraint("student_id", "key", name="uq_student_pref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[str] = mapped_column(String(255))

    student = relationship("Student", back_populates="preferences")


class College(Base):
    __tablename__ = "colleges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    location: Mapped[str] = mapped_column(String(120), default="Assam")


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)


class SeatCategory(Base):
    __tablename__ = "seat_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(120))


class YearlyCutoff(Base):
    __tablename__ = "yearly_cutoffs"
    __table_args__ = (
        UniqueConstraint(
            "college_id",
            "branch_id",
            "category_id",
            "exam_year",
            name="uq_cutoff_dimensions",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("seat_categories.id"), index=True)
    exam_type: Mapped[str] = mapped_column(String(20), index=True)
    exam_year: Mapped[int] = mapped_column(Integer, index=True)
    opening_rank: Mapped[int] = mapped_column(Integer)
    closing_rank: Mapped[int] = mapped_column(Integer)
    seat_type: Mapped[str] = mapped_column(String(30), default="Government")


class PlacementStat(Base):
    __tablename__ = "placement_stats"
    __table_args__ = (UniqueConstraint("college_id", "branch_id", "report_year", name="uq_placement_yearly"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    college_id: Mapped[int] = mapped_column(ForeignKey("colleges.id"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    report_year: Mapped[int] = mapped_column(Integer, index=True)
    placement_rate: Mapped[float] = mapped_column(Float)
    median_salary_lpa: Mapped[float] = mapped_column(Float)
    top_recruiters: Mapped[str] = mapped_column(Text, default="")


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str] = mapped_column(String(500), default="")
    checksum: Mapped[str] = mapped_column(String(128), index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EmbeddingChunk(Base):
    __tablename__ = "embedding_chunks"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    source_document_id: Mapped[str] = mapped_column(ForeignKey("source_documents.id"), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    vector_ref: Mapped[str] = mapped_column(String(120), index=True)
