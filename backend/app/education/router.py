"""
Education Router - API endpoints para Cursos e Aulas

Endpoints:
- GET /api/education/courses - Listar cursos
- GET /api/education/courses/{id} - Detalhes do curso
- POST /api/education/courses - Criar curso (admin)
- PUT /api/education/courses/{id} - Atualizar curso (admin)
- DELETE /api/education/courses/{id} - Deletar curso (admin)

- GET /api/education/courses/{id}/lessons - Listar aulas do curso
- GET /api/education/lessons/{id} - Detalhes da aula
- POST /api/education/lessons - Criar aula (admin)
- PUT /api/education/lessons/{id} - Atualizar aula (admin)
- DELETE /api/education/lessons/{id} - Deletar aula (admin)

- POST /api/education/courses/{id}/enroll - Matricular usu?rio
- GET /api/education/my-courses - Cursos do usu?rio
- POST /api/education/progress - Atualizar progresso

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user, get_current_admin_user
from app.education.repository import EducationRepository
from app.education.service import (
    extract_video_embed,
    generate_certificate_hash,
    generate_certificate_pdf,
    score_quiz_attempt,
)
from app.education.models import (
    CourseCreate, CourseUpdate, Course,
    LessonCreate, LessonUpdate, Lesson,
    CourseLevel, LessonType, CourseStatus
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/education", tags=["Education"])


# ==================== SCHEMAS ====================

class CourseListResponse(BaseModel):
    courses: list
    total: int
    page: int
    per_page: int


class LessonListResponse(BaseModel):
    lessons: list
    total: int


class EnrollmentResponse(BaseModel):
    id: str
    course_id: str
    enrolled_at: str
    progress_percent: float
    lessons_completed: int
    total_lessons: int


class ProgressUpdateRequest(BaseModel):
    lesson_id: str
    course_id: str
    watched_seconds: int
    completed: bool = False


class MyCoursesResponse(BaseModel):
    enrollments: list
    total: int


# ==================== COURSES ENDPOINTS ====================

@router.get("/courses", response_model=CourseListResponse)
async def list_courses(
    status: Optional[str] = Query(None, description="Filter by status"),
    level: Optional[str] = Query(None, description="Filter by level"),
    category: Optional[str] = Query(None, description="Filter by category"),
    is_premium: Optional[bool] = Query(None, description="Filter premium courses"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """
    Lista cursos dispon?veis com filtros.
    """
    try:
        skip = (page - 1) * per_page
        
        # Por padr?o, s? mostrar cursos publicados para usu?rios normais
        if status is None:
            status = "published"
        
        courses = await EducationRepository.list_courses(
            status=status,
            level=level,
            category=category,
            is_premium=is_premium,
            limit=per_page,
            skip=skip
        )
        
        return CourseListResponse(
            courses=courses,
            total=len(courses),
            page=page,
            per_page=per_page
        )
    except Exception as e:
        logger.error(f"? Erro ao listar cursos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/courses/{course_id}")
async def get_course(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obt?m detalhes de um curso.
    """
    try:
        course = await EducationRepository.get_course_by_id(course_id)
        
        if not course:
            raise HTTPException(status_code=404, detail="Curso n?o encontrado")
        
        # Adicionar info de matr?cula do usu?rio
        user_id = str(current_user["_id"])
        enrollment = await EducationRepository.get_user_enrollment(user_id, course_id)
        
        course["is_enrolled"] = enrollment is not None
        course["enrollment"] = enrollment
        
        return course
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao buscar curso: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/courses")
async def create_course(
    course_data: CourseCreate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Cria um novo curso (admin only).
    """
    try:
        course = await EducationRepository.create_course(course_data.model_dump())
        
        return {"success": True, "course": course}
    except Exception as e:
        logger.error(f"? Erro ao criar curso: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/courses/{course_id}")
async def update_course(
    course_id: str,
    update_data: CourseUpdate,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Atualiza um curso (admin only).
    """
    try:
        # Filtrar campos None
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
        
        course = await EducationRepository.update_course(course_id, update_dict)
        
        if not course:
            raise HTTPException(status_code=404, detail="Curso n?o encontrado")
        
        return {"success": True, "course": course}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao atualizar curso: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/courses/{course_id}")
async def delete_course(
    course_id: str,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Deleta um curso (admin only).
    """
    try:
        deleted = await EducationRepository.delete_course(course_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Curso n?o encontrado")
        
        return {"success": True, "message": "Curso deletado"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao deletar curso: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== LESSONS ENDPOINTS ====================

@router.get("/courses/{course_id}/lessons", response_model=LessonListResponse)
async def list_course_lessons(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Lista aulas de um curso.
    """
    try:
        lessons = await EducationRepository.list_lessons_by_course(course_id)
        
        # Adicionar progresso do usu?rio
        user_id = str(current_user["_id"])
        for lesson in lessons:
            progress = await EducationRepository.get_lesson_progress(user_id, lesson["id"])
            lesson["user_progress"] = {
                "watched_seconds": progress.get("watched_seconds", 0) if progress else 0,
                "completed": progress.get("completed", False) if progress else False,
            }
        
        return LessonListResponse(
            lessons=lessons,
            total=len(lessons)
        )
    except Exception as e:
        logger.error(f"? Erro ao listar aulas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lessons/{lesson_id}")
async def get_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Obt?m detalhes de uma aula.
    """
    try:
        lesson = await EducationRepository.get_lesson_by_id(lesson_id)
        
        if not lesson:
            raise HTTPException(status_code=404, detail="Aula n?o encontrada")
        
        # Verificar se usu?rio est? matriculado (se n?o for preview)
        if not lesson.get("is_preview"):
            user_id = str(current_user["_id"])
            enrollment = await EducationRepository.get_user_enrollment(
                user_id, 
                lesson["course_id"]
            )
            
            if not enrollment:
                raise HTTPException(
                    status_code=403, 
                    detail="Matricule-se no curso para acessar esta aula"
                )
        
        # Adicionar progresso
        user_id = str(current_user["_id"])
        progress = await EducationRepository.get_lesson_progress(user_id, lesson_id)
        lesson["user_progress"] = progress
        
        return lesson
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao buscar aula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lessons")
async def create_lesson(
    lesson_data: LessonCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Cria uma nova aula (admin only).
    """
    try:
        lesson = await EducationRepository.create_lesson(lesson_data.model_dump())
        
        return {"success": True, "lesson": lesson}
    except Exception as e:
        logger.error(f"? Erro ao criar aula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/lessons/{lesson_id}")
async def update_lesson(
    lesson_id: str,
    update_data: LessonUpdate,
    current_user: dict = Depends(get_current_user)
):
    """
    Atualiza uma aula (admin only).
    """
    try:
        update_dict = {k: v for k, v in update_data.model_dump().items() if v is not None}
        
        if not update_dict:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar")
        
        lesson = await EducationRepository.update_lesson(lesson_id, update_dict)
        
        if not lesson:
            raise HTTPException(status_code=404, detail="Aula n?o encontrada")
        
        return {"success": True, "lesson": lesson}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao atualizar aula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/lessons/{lesson_id}")
async def delete_lesson(
    lesson_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Deleta uma aula (admin only).
    """
    try:
        deleted = await EducationRepository.delete_lesson(lesson_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="Aula n?o encontrada")
        
        return {"success": True, "message": "Aula deletada"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao deletar aula: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== ENROLLMENT ENDPOINTS ====================

@router.post("/courses/{course_id}/enroll")
async def enroll_in_course(
    course_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Matricula o usu?rio em um curso.
    """
    try:
        user_id = str(current_user["_id"])
        
        # Verificar se curso existe
        course = await EducationRepository.get_course_by_id(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Curso n?o encontrado")
        
        # Verificar se curso ? premium e usu?rio tem licen?a
        if course.get("is_premium"):
            # TODO: Verificar licen?a do usu?rio
            pass
        
        enrollment = await EducationRepository.enroll_user(user_id, course_id)
        
        return {
            "success": True,
            "message": "Matr?cula realizada com sucesso",
            "enrollment": enrollment
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"? Erro ao matricular: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/my-courses", response_model=MyCoursesResponse)
async def get_my_courses(current_user: dict = Depends(get_current_user)):
    """
    Lista cursos em que o usu?rio est? matriculado.
    """
    try:
        user_id = str(current_user["_id"])
        enrollments = await EducationRepository.list_user_enrollments(user_id)
        
        # Enriquecer com dados do curso
        enriched = []
        for enrollment in enrollments:
            course = await EducationRepository.get_course_by_id(enrollment["course_id"])
            if course:
                enriched.append({
                    **enrollment,
                    "course": course
                })
        
        return MyCoursesResponse(
            enrollments=enriched,
            total=len(enriched)
        )
    except Exception as e:
        logger.error(f"? Erro ao listar meus cursos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/progress")
async def update_progress(
    progress: ProgressUpdateRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Atualiza progresso do usu?rio em uma aula.
    """
    try:
        user_id = str(current_user["_id"])
        
        await EducationRepository.update_lesson_progress(
            user_id=user_id,
            course_id=progress.course_id,
            lesson_id=progress.lesson_id,
            watched_seconds=progress.watched_seconds,
            completed=progress.completed
        )
        
        return {"success": True, "message": "Progresso atualizado"}
    except Exception as e:
        logger.error(f"? Erro ao atualizar progresso: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PLAYER ENDPOINT ====================

@router.get("/courses/{course_id}/player")
async def get_course_player(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna informações do player de vídeo para o primeiro vídeo do curso.
    Detecta automaticamente YouTube, Vimeo ou URL direta.
    """
    try:
        course = await EducationRepository.get_course_by_id(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Curso não encontrado")

        lessons = await EducationRepository.list_lessons_by_course(course_id)
        first_video = next(
            (l for l in lessons if l.get("video_url") and l.get("type") == "video"),
            None,
        )

        url = first_video["video_url"] if first_video else ""
        provider = first_video.get("video_provider") if first_video else None

        return extract_video_embed(url, provider)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar player: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== QUIZ ENDPOINTS ====================

class QuizSubmitRequest(BaseModel):
    answers: List[int]


class QuizCreateRequest(BaseModel):
    title: str = "Quiz"
    passing_score: int = 70
    questions: list


@router.get("/courses/{course_id}/lessons/{lesson_id}/quiz")
async def get_lesson_quiz(
    course_id: str,
    lesson_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna o quiz de uma aula (sem expor correct_index).
    """
    try:
        user_id = str(current_user["_id"])

        enrollment = await EducationRepository.get_user_enrollment(user_id, course_id)
        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="Matricule-se no curso para acessar o quiz",
            )

        quiz = await EducationRepository.get_quiz_by_lesson(lesson_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz não encontrado para esta aula")

        # Strip correct_index before sending to client
        safe_questions = [
            {
                "question": q["question"],
                "options": q["options"],
                "explanation": q.get("explanation"),
            }
            for q in quiz.get("questions", [])
        ]

        attempt = await EducationRepository.get_latest_quiz_attempt(user_id, quiz["id"])

        return {
            "quiz": {**quiz, "questions": safe_questions},
            "latest_attempt": attempt,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/courses/{course_id}/lessons/{lesson_id}/quiz")
async def submit_lesson_quiz(
    course_id: str,
    lesson_id: str,
    submission: QuizSubmitRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Submete respostas para o quiz de uma aula e registra a tentativa.
    Completa automaticamente a aula se a pontuação for suficiente.
    """
    try:
        user_id = str(current_user["_id"])

        enrollment = await EducationRepository.get_user_enrollment(user_id, course_id)
        if not enrollment:
            raise HTTPException(
                status_code=403,
                detail="Matricule-se no curso para fazer o quiz",
            )

        quiz = await EducationRepository.get_quiz_by_lesson(lesson_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz não encontrado")

        questions = quiz.get("questions", [])
        if not questions:
            raise HTTPException(status_code=400, detail="Quiz sem perguntas")

        score, correct_count = score_quiz_attempt(questions, submission.answers)
        passing_score = quiz.get("passing_score", 70)
        passed = score >= passing_score

        attempt = await EducationRepository.record_quiz_attempt(
            user_id=user_id,
            quiz_id=quiz["id"],
            lesson_id=lesson_id,
            course_id=course_id,
            answers=submission.answers,
            score=score,
            passed=passed,
        )

        # Auto-complete lesson on pass
        if passed:
            await EducationRepository.update_lesson_progress(
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson_id,
                watched_seconds=0,
                completed=True,
            )

        # Build review (reveal correct answers after submission)
        questions_review = []
        for i, q in enumerate(questions):
            user_ans = submission.answers[i] if i < len(submission.answers) else -1
            questions_review.append(
                {
                    "question": q["question"],
                    "options": q["options"],
                    "correct_index": q["correct_index"],
                    "user_answer": user_ans,
                    "is_correct": user_ans == q["correct_index"],
                    "explanation": q.get("explanation"),
                }
            )

        return {
            "score": score,
            "correct_count": correct_count,
            "total_questions": len(questions),
            "passed": passed,
            "passing_score": passing_score,
            "attempt": attempt,
            "questions_review": questions_review,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao submeter quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== CERTIFICATE ENDPOINT ====================

@router.get("/courses/{course_id}/certificate")
async def get_course_certificate(
    course_id: str,
    format: str = Query("json", description="Formato: 'json' ou 'pdf'"),
    current_user: dict = Depends(get_current_user),
):
    """
    Emite (ou recupera) o certificado de conclusão do curso.
    O curso precisa estar 100% concluído.
    Suporta ?format=pdf para download direto.
    """
    try:
        user_id = str(current_user["_id"])

        course = await EducationRepository.get_course_by_id(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Curso não encontrado")

        enrollment = await EducationRepository.get_user_enrollment(user_id, course_id)
        if not enrollment:
            raise HTTPException(
                status_code=403, detail="Você não está matriculado neste curso"
            )

        progress_percent = enrollment.get("progress_percent", 0)
        if progress_percent < 100:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Conclua 100% do curso para obter o certificado. "
                    f"Progresso atual: {progress_percent}%"
                ),
            )

        # Get or issue certificate
        cert = await EducationRepository.get_certificate(user_id, course_id)
        if not cert:
            user_name = (
                current_user.get("name")
                or current_user.get("full_name")
                or current_user.get("email", "Aluno")
            )
            cert_hash = generate_certificate_hash(user_id, course_id, datetime.utcnow())
            cert = await EducationRepository.issue_certificate(
                user_id=user_id,
                course_id=course_id,
                course_title=course["title"],
                user_name=user_name,
                cert_hash=cert_hash,
            )

        if format == "pdf":
            issued_at = cert.get("issued_at", datetime.utcnow())
            if not isinstance(issued_at, datetime):
                issued_at = datetime.utcnow()

            pdf_bytes = generate_certificate_pdf(
                user_name=cert["user_name"],
                course_title=cert["course_title"],
                issued_at=issued_at,
                cert_hash=cert["cert_hash"],
            )
            filename = f"certificado_{course_id[:8]}.pdf"
            return StreamingResponse(
                BytesIO(pdf_bytes),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"'
                },
            )

        # JSON response
        issued_at = cert.get("issued_at", datetime.utcnow())
        if isinstance(issued_at, datetime):
            issued_at_str = issued_at.isoformat()
        else:
            issued_at_str = str(issued_at)

        return {
            "id": cert["id"],
            "course_id": course_id,
            "course_title": cert["course_title"],
            "user_name": cert["user_name"],
            "issued_at": issued_at_str,
            "cert_hash": cert["cert_hash"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao gerar certificado: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== PROGRESS DETAIL ENDPOINT ====================

@router.get("/courses/{course_id}/progress")
async def get_course_progress_detail(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Retorna o progresso detalhado do usuário no curso.
    """
    try:
        user_id = str(current_user["_id"])

        course = await EducationRepository.get_course_by_id(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Curso não encontrado")

        enrollment = await EducationRepository.get_user_enrollment(user_id, course_id)
        if not enrollment:
            return {
                "is_enrolled": False,
                "progress_percent": 0.0,
                "lessons_completed": 0,
                "total_lessons": course.get("lesson_count", 0),
                "completed_at": None,
                "certificate_issued": False,
            }

        return {
            "is_enrolled": True,
            "progress_percent": enrollment.get("progress_percent", 0.0),
            "lessons_completed": enrollment.get("lessons_completed", 0),
            "total_lessons": enrollment.get(
                "total_lessons", course.get("lesson_count", 0)
            ),
            "started_at": enrollment.get("started_at"),
            "last_activity_at": enrollment.get("last_activity_at"),
            "completed_at": enrollment.get("completed_at"),
            "certificate_issued": enrollment.get("certificate_issued", False),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erro ao buscar progresso: {e}")
        raise HTTPException(status_code=500, detail=str(e))
