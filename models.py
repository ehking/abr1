#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLAlchemy models for:
- Project
- Job
- Media

SQLite database is created automatically (app.db).
"""

import os
import datetime
from typing import Optional

from sqlalchemy import (
    create_engine, Column, Integer, String,
    DateTime, Text, ForeignKey
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "app.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()

def get_session():
    return SessionLocal()

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    audio_path = Column(Text, nullable=False)
    video_path = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.now)

    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    medias = relationship("Media", back_populates="project", cascade="all, delete-orphan")

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(64), nullable=False, unique=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    audio_path = Column(Text, nullable=False)
    video_path = Column(Text, nullable=False)
    output_path = Column(Text, nullable=True)

    status = Column(String(32), default="queued")  # queued, running, done, error
    progress = Column(Integer, default=0)
    message = Column(Text, default="")
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.now)
    updated_at = Column(DateTime, default=datetime.datetime.now)

    project = relationship("Project", back_populates="jobs")
    medias = relationship("Media", back_populates="job")

    def to_dict(self):
        return {
            "id": self.id,
            "uuid": self.uuid,
            "project_id": self.project_id,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "output_path": self.output_path,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "created_at": self.created_at.isoformat(sep=" ", timespec="seconds") if self.created_at else None,
            "updated_at": self.updated_at.isoformat(sep=" ", timespec="seconds") if self.updated_at else None,
        }

class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=True)

    file_path = Column(Text, nullable=False)
    media_type = Column(String(32), default="video")  # video, image, audio, ...
    created_at = Column(DateTime, default=datetime.datetime.now)

    project = relationship("Project", back_populates="medias")
    job = relationship("Job", back_populates="medias")
