"""
Education Module - Cursos, Aulas e Progresso
"""

from app.education.models import (
    Course, CourseCreate, CourseUpdate, CourseLevel, CourseStatus,
    Lesson, LessonCreate, LessonUpdate, LessonType,
    CourseProgress, LessonProgress, CourseEnrollment,
    Quiz, QuizCreate, QuizSubmission, QuizAttempt, QuizQuestion,
    Certificate, PlayerInfo,
)
from app.education.repository import EducationRepository
from app.education.router import router as education_router
from app.education.service import (
    extract_video_embed,
    score_quiz_attempt,
    generate_certificate_hash,
    generate_certificate_pdf,
)

education_repository = EducationRepository()

__all__ = [
    # Models
    "Course", "CourseCreate", "CourseUpdate", "CourseLevel", "CourseStatus",
    "Lesson", "LessonCreate", "LessonUpdate", "LessonType",
    "CourseProgress", "LessonProgress", "CourseEnrollment",
    "Quiz", "QuizCreate", "QuizSubmission", "QuizAttempt", "QuizQuestion",
    "Certificate", "PlayerInfo",
    # Repository
    "EducationRepository",
    # Service
    "extract_video_embed", "score_quiz_attempt",
    "generate_certificate_hash", "generate_certificate_pdf",
    # Router
    "education_router",
]
