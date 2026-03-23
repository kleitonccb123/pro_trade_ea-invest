"""
Education Module - Modelo de dados para Cursos e Aulas

Collections:
- courses: Cursos de trading
- lessons: Aulas individuais
- user_progress: Progresso do usu?rio

Author: Crypto Trade Hub
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from enum import Enum


class CourseLevel(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class LessonType(str, Enum):
    VIDEO = "video"
    ARTICLE = "article"
    QUIZ = "quiz"
    INTERACTIVE = "interactive"


class CourseStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


# ==================== COURSE MODELS ====================

class CourseCreate(BaseModel):
    """Modelo para criar um curso."""
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10)
    thumbnail_url: Optional[str] = None
    level: CourseLevel = CourseLevel.BEGINNER
    category: str = Field(default="trading")
    tags: List[str] = Field(default_factory=list)
    estimated_duration: int = Field(default=60, description="Dura??o em minutos")
    is_premium: bool = False
    required_license: Optional[str] = None  # "starter", "pro", etc.
    instructor_name: Optional[str] = None
    instructor_avatar: Optional[str] = None


class Course(CourseCreate):
    """Modelo completo de curso."""
    id: str
    status: CourseStatus = CourseStatus.DRAFT
    lesson_count: int = 0
    enrolled_count: int = 0
    rating: float = 0.0
    review_count: int = 0
    created_at: datetime
    updated_at: datetime
    published_at: Optional[datetime] = None


class CourseUpdate(BaseModel):
    """Modelo para atualizar um curso."""
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    level: Optional[CourseLevel] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    estimated_duration: Optional[int] = None
    is_premium: Optional[bool] = None
    required_license: Optional[str] = None
    status: Optional[CourseStatus] = None


# ==================== LESSON MODELS ====================

class LessonCreate(BaseModel):
    """Modelo para criar uma aula."""
    course_id: str
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = None
    type: LessonType = LessonType.VIDEO
    order: int = Field(default=0, ge=0)
    
    # Conte?do de v?deo
    video_url: Optional[str] = None
    video_duration: Optional[int] = None  # segundos
    video_provider: Optional[str] = None  # youtube, vimeo, etc.
    
    # Conte?do de artigo
    content_html: Optional[str] = None
    content_markdown: Optional[str] = None
    
    # Configura??es
    is_preview: bool = False  # Pode ser visto sem assinatura
    is_downloadable: bool = False
    resources: List[dict] = Field(default_factory=list)  # PDFs, links, etc.


class Lesson(LessonCreate):
    """Modelo completo de aula."""
    id: str
    slug: str
    view_count: int = 0
    completion_count: int = 0
    created_at: datetime
    updated_at: datetime


class LessonUpdate(BaseModel):
    """Modelo para atualizar uma aula."""
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[LessonType] = None
    order: Optional[int] = None
    video_url: Optional[str] = None
    video_duration: Optional[int] = None
    content_html: Optional[str] = None
    content_markdown: Optional[str] = None
    is_preview: Optional[bool] = None
    is_downloadable: Optional[bool] = None
    resources: Optional[List[dict]] = None


# ==================== PROGRESS MODELS ====================

class LessonProgress(BaseModel):
    """Progresso do usu?rio em uma aula."""
    lesson_id: str
    watched_seconds: int = 0
    completed: bool = False
    completed_at: Optional[datetime] = None
    last_watched_at: datetime


class CourseProgress(BaseModel):
    """Progresso do usu?rio em um curso."""
    user_id: str
    course_id: str
    lessons_completed: int = 0
    total_lessons: int = 0
    progress_percent: float = 0.0
    started_at: datetime
    last_activity_at: datetime
    completed_at: Optional[datetime] = None
    certificate_issued: bool = False


class CourseEnrollment(BaseModel):
    """Matr?cula do usu?rio em um curso."""
    user_id: str
    course_id: str
    enrolled_at: datetime
    progress: CourseProgress
    lessons: List[LessonProgress] = Field(default_factory=list)

# ==================== QUIZ MODELS ====================

class QuizQuestion(BaseModel):
    """Uma questão de quiz com múltipla escolha."""
    question: str
    options: List[str] = Field(..., min_length=2)
    correct_index: int = Field(..., ge=0)
    explanation: Optional[str] = None


class QuizCreate(BaseModel):
    """Modelo para criar um quiz."""
    lesson_id: str
    course_id: str
    title: str = "Quiz"
    passing_score: int = Field(default=70, ge=0, le=100)
    questions: List[QuizQuestion] = Field(default_factory=list)


class Quiz(QuizCreate):
    """Modelo completo de quiz."""
    id: str
    created_at: datetime
    updated_at: datetime


class QuizSubmission(BaseModel):
    """Submissão de respostas de quiz."""
    answers: List[int] = Field(..., description="Índices das respostas escolhidas")


class QuizAttempt(BaseModel):
    """Tentativa de quiz registrada."""
    id: str
    user_id: str
    quiz_id: str
    lesson_id: str
    course_id: str
    answers: List[int]
    score: int
    passed: bool
    attempted_at: datetime


# ==================== CERTIFICATE MODELS ====================

class Certificate(BaseModel):
    """Certificado de conclusão de curso."""
    id: str
    user_id: str
    course_id: str
    course_title: str
    user_name: str
    issued_at: datetime
    cert_hash: str



class Quiz(QuizCreate):
    """Modelo completo de quiz."""
    id: str
    created_at: datetime
    updated_at: datetime


class QuizSubmission(BaseModel):
    """Submissão de respostas de um quiz."""
    answers: List[int] = Field(..., description="Índice da opção escolhida por pergunta")


class QuizAttempt(BaseModel):
    """Tentativa de quiz de um usuário."""
    id: str
    user_id: str
    quiz_id: str
    lesson_id: str
    course_id: str
    answers: List[int]
    score: float
    passed: bool
    attempted_at: datetime


# ==================== CERTIFICATE MODELS ====================

class Certificate(BaseModel):
    """Certificado de conclusão emitido para o usuário."""
    id: str
    user_id: str
    course_id: str
    course_title: str
    user_name: str
    issued_at: datetime
    cert_hash: str


# ==================== PLAYER MODEL ====================

class PlayerInfo(BaseModel):
    """Informações do player de vídeo (embed ou direto)."""
    embed_url: str
    provider: str  # "youtube", "vimeo", "direct"
    video_id: str
    original_url: str