"""
Education Repository - CRUD para Cursos, Aulas e Progresso

MongoDB Collections:
- courses: Lista de cursos
- lessons: Aulas por curso
- enrollments: Matr?culas de usu?rios
- user_lesson_progress: Progresso detalhado por aula

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional, List
from bson import ObjectId

from app.core.database import get_db

logger = logging.getLogger(__name__)


def generate_slug(title: str) -> str:
    """Gera slug a partir do t?tulo."""
    slug = title.lower().strip()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    return slug[:100]


class EducationRepository:
    """Reposit?rio para opera??es de educa??o no MongoDB."""
    
    COURSES_COLLECTION = "courses"
    LESSONS_COLLECTION = "lessons"
    ENROLLMENTS_COLLECTION = "enrollments"
    PROGRESS_COLLECTION = "user_lesson_progress"
    
    @classmethod
    def _get_courses_collection(cls):
        db = get_db()
        return db[cls.COURSES_COLLECTION]
    
    @classmethod
    def _get_lessons_collection(cls):
        db = get_db()
        return db[cls.LESSONS_COLLECTION]
    
    @classmethod
    def _get_enrollments_collection(cls):
        db = get_db()
        return db[cls.ENROLLMENTS_COLLECTION]
    
    @classmethod
    def _get_progress_collection(cls):
        db = get_db()
        return db[cls.PROGRESS_COLLECTION]
    
    # ==================== COURSES ====================
    
    @classmethod
    async def create_course(cls, course_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um novo curso."""
        collection = cls._get_courses_collection()
        
        now = datetime.utcnow()
        course_doc = {
            **course_data,
            "slug": generate_slug(course_data["title"]),
            "status": course_data.get("status", "draft"),
            "lesson_count": 0,
            "enrolled_count": 0,
            "rating": 0.0,
            "review_count": 0,
            "created_at": now,
            "updated_at": now,
            "published_at": None,
        }
        
        result = await collection.insert_one(course_doc)
        course_doc["_id"] = result.inserted_id
        
        logger.info(f"? Curso criado: {course_doc['title']}")
        return cls._serialize_course(course_doc)
    
    @classmethod
    async def get_course_by_id(cls, course_id: str) -> Optional[Dict[str, Any]]:
        """Busca curso por ID."""
        collection = cls._get_courses_collection()
        
        try:
            course = await collection.find_one({"_id": ObjectId(course_id)})
            return cls._serialize_course(course) if course else None
        except:
            return None
    
    @classmethod
    async def get_course_by_slug(cls, slug: str) -> Optional[Dict[str, Any]]:
        """Busca curso por slug."""
        collection = cls._get_courses_collection()
        course = await collection.find_one({"slug": slug})
        return cls._serialize_course(course) if course else None
    
    @classmethod
    async def list_courses(
        cls,
        status: Optional[str] = None,
        level: Optional[str] = None,
        category: Optional[str] = None,
        is_premium: Optional[bool] = None,
        limit: int = 50,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Lista cursos com filtros."""
        collection = cls._get_courses_collection()
        
        filter_query = {}
        if status:
            filter_query["status"] = status
        if level:
            filter_query["level"] = level
        if category:
            filter_query["category"] = category
        if is_premium is not None:
            filter_query["is_premium"] = is_premium
        
        cursor = collection.find(filter_query).sort("created_at", -1).skip(skip).limit(limit)
        courses = await cursor.to_list(length=limit)
        
        return [cls._serialize_course(c) for c in courses]
    
    @classmethod
    async def update_course(cls, course_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Atualiza um curso."""
        collection = cls._get_courses_collection()
        
        update_data["updated_at"] = datetime.utcnow()
        
        # Se t?tulo mudou, atualizar slug
        if "title" in update_data:
            update_data["slug"] = generate_slug(update_data["title"])
        
        # Se publicando, definir data de publica??o
        if update_data.get("status") == "published":
            update_data["published_at"] = datetime.utcnow()
        
        result = await collection.find_one_and_update(
            {"_id": ObjectId(course_id)},
            {"$set": update_data},
            return_document=True
        )
        
        return cls._serialize_course(result) if result else None
    
    @classmethod
    async def delete_course(cls, course_id: str) -> bool:
        """Deleta um curso e suas aulas."""
        courses_col = cls._get_courses_collection()
        lessons_col = cls._get_lessons_collection()
        
        try:
            oid = ObjectId(course_id)
            
            # Deletar aulas do curso
            await lessons_col.delete_many({"course_id": course_id})
            
            # Deletar curso
            result = await courses_col.delete_one({"_id": oid})
            
            return result.deleted_count > 0
        except:
            return False
    
    @classmethod
    def _serialize_course(cls, course: Dict[str, Any]) -> Dict[str, Any]:
        """Serializa documento de curso."""
        if not course:
            return None
        doc = dict(course)
        doc["id"] = str(doc.pop("_id"))
        return doc
    
    # ==================== LESSONS ====================
    
    @classmethod
    async def create_lesson(cls, lesson_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria uma nova aula."""
        collection = cls._get_lessons_collection()
        courses_col = cls._get_courses_collection()
        
        now = datetime.utcnow()
        lesson_doc = {
            **lesson_data,
            "slug": generate_slug(lesson_data["title"]),
            "view_count": 0,
            "completion_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        
        result = await collection.insert_one(lesson_doc)
        lesson_doc["_id"] = result.inserted_id
        
        # Incrementar contador de aulas no curso
        await courses_col.update_one(
            {"_id": ObjectId(lesson_data["course_id"])},
            {"$inc": {"lesson_count": 1}}
        )
        
        logger.info(f"? Aula criada: {lesson_doc['title']}")
        return cls._serialize_lesson(lesson_doc)
    
    @classmethod
    async def get_lesson_by_id(cls, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Busca aula por ID."""
        collection = cls._get_lessons_collection()
        
        try:
            lesson = await collection.find_one({"_id": ObjectId(lesson_id)})
            return cls._serialize_lesson(lesson) if lesson else None
        except:
            return None
    
    @classmethod
    async def list_lessons_by_course(
        cls,
        course_id: str,
        limit: int = 100,
        skip: int = 0
    ) -> List[Dict[str, Any]]:
        """Lista aulas de um curso ordenadas."""
        collection = cls._get_lessons_collection()
        
        cursor = collection.find({"course_id": course_id}).sort("order", 1).skip(skip).limit(limit)
        lessons = await cursor.to_list(length=limit)
        
        return [cls._serialize_lesson(l) for l in lessons]
    
    @classmethod
    async def update_lesson(cls, lesson_id: str, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Atualiza uma aula."""
        collection = cls._get_lessons_collection()
        
        update_data["updated_at"] = datetime.utcnow()
        
        if "title" in update_data:
            update_data["slug"] = generate_slug(update_data["title"])
        
        result = await collection.find_one_and_update(
            {"_id": ObjectId(lesson_id)},
            {"$set": update_data},
            return_document=True
        )
        
        return cls._serialize_lesson(result) if result else None
    
    @classmethod
    async def delete_lesson(cls, lesson_id: str) -> bool:
        """Deleta uma aula."""
        collection = cls._get_lessons_collection()
        courses_col = cls._get_courses_collection()
        
        try:
            lesson = await collection.find_one({"_id": ObjectId(lesson_id)})
            if not lesson:
                return False
            
            # Deletar aula
            result = await collection.delete_one({"_id": ObjectId(lesson_id)})
            
            # Decrementar contador de aulas no curso
            if result.deleted_count > 0:
                await courses_col.update_one(
                    {"_id": ObjectId(lesson["course_id"])},
                    {"$inc": {"lesson_count": -1}}
                )
            
            return result.deleted_count > 0
        except:
            return False
    
    @classmethod
    async def reorder_lessons(cls, course_id: str, lesson_orders: List[Dict[str, int]]) -> bool:
        """Reordena aulas de um curso."""
        collection = cls._get_lessons_collection()
        
        try:
            for item in lesson_orders:
                await collection.update_one(
                    {"_id": ObjectId(item["lesson_id"]), "course_id": course_id},
                    {"$set": {"order": item["order"]}}
                )
            return True
        except Exception as e:
            logger.error(f"? Erro ao reordenar aulas: {e}")
            return False
    
    @classmethod
    def _serialize_lesson(cls, lesson: Dict[str, Any]) -> Dict[str, Any]:
        """Serializa documento de aula."""
        if not lesson:
            return None
        doc = dict(lesson)
        doc["id"] = str(doc.pop("_id"))
        return doc
    
    # ==================== ENROLLMENTS & PROGRESS ====================
    
    @classmethod
    async def enroll_user(cls, user_id: str, course_id: str) -> Dict[str, Any]:
        """Matricula um usu?rio em um curso."""
        collection = cls._get_enrollments_collection()
        courses_col = cls._get_courses_collection()
        
        # Verificar se j? est? matriculado
        existing = await collection.find_one({
            "user_id": user_id,
            "course_id": course_id
        })
        
        if existing:
            return cls._serialize_enrollment(existing)
        
        # Buscar total de aulas
        course = await cls.get_course_by_id(course_id)
        total_lessons = course.get("lesson_count", 0) if course else 0
        
        now = datetime.utcnow()
        enrollment_doc = {
            "user_id": user_id,
            "course_id": course_id,
            "enrolled_at": now,
            "lessons_completed": 0,
            "total_lessons": total_lessons,
            "progress_percent": 0.0,
            "started_at": now,
            "last_activity_at": now,
            "completed_at": None,
            "certificate_issued": False,
        }
        
        result = await collection.insert_one(enrollment_doc)
        enrollment_doc["_id"] = result.inserted_id
        
        # Incrementar contador de matriculados
        await courses_col.update_one(
            {"_id": ObjectId(course_id)},
            {"$inc": {"enrolled_count": 1}}
        )
        
        logger.info(f"? Usu?rio {user_id} matriculado no curso {course_id}")
        return cls._serialize_enrollment(enrollment_doc)
    
    @classmethod
    async def get_user_enrollment(cls, user_id: str, course_id: str) -> Optional[Dict[str, Any]]:
        """Busca matr?cula de um usu?rio em um curso."""
        collection = cls._get_enrollments_collection()
        
        enrollment = await collection.find_one({
            "user_id": user_id,
            "course_id": course_id
        })
        
        return cls._serialize_enrollment(enrollment) if enrollment else None
    
    @classmethod
    async def list_user_enrollments(cls, user_id: str) -> List[Dict[str, Any]]:
        """Lista todas as matr?culas de um usu?rio."""
        collection = cls._get_enrollments_collection()
        
        cursor = collection.find({"user_id": user_id}).sort("enrolled_at", -1)
        enrollments = await cursor.to_list(length=100)
        
        return [cls._serialize_enrollment(e) for e in enrollments]
    
    @classmethod
    async def update_lesson_progress(
        cls,
        user_id: str,
        course_id: str,
        lesson_id: str,
        watched_seconds: int,
        completed: bool = False
    ) -> Dict[str, Any]:
        """Atualiza progresso em uma aula."""
        progress_col = cls._get_progress_collection()
        enrollments_col = cls._get_enrollments_collection()
        lessons_col = cls._get_lessons_collection()
        
        now = datetime.utcnow()
        
        # Atualizar/criar progresso da aula
        progress = await progress_col.find_one_and_update(
            {"user_id": user_id, "lesson_id": lesson_id},
            {
                "$set": {
                    "course_id": course_id,
                    "watched_seconds": watched_seconds,
                    "completed": completed,
                    "last_watched_at": now,
                    "completed_at": now if completed else None,
                },
                "$setOnInsert": {
                    "user_id": user_id,
                    "lesson_id": lesson_id,
                    "started_at": now,
                }
            },
            upsert=True,
            return_document=True
        )
        
        # Incrementar view count se primeira vez
        if progress.get("started_at") == now:
            await lessons_col.update_one(
                {"_id": ObjectId(lesson_id)},
                {"$inc": {"view_count": 1}}
            )
        
        # Se completou, incrementar completion count
        if completed and progress.get("completed_at") == now:
            await lessons_col.update_one(
                {"_id": ObjectId(lesson_id)},
                {"$inc": {"completion_count": 1}}
            )
        
        # Recalcular progresso do curso
        await cls._recalculate_course_progress(user_id, course_id)
        
        return progress
    
    @classmethod
    async def _recalculate_course_progress(cls, user_id: str, course_id: str):
        """Recalcula o progresso total do usu?rio no curso."""
        progress_col = cls._get_progress_collection()
        enrollments_col = cls._get_enrollments_collection()
        
        # Contar aulas completadas
        completed_count = await progress_col.count_documents({
            "user_id": user_id,
            "course_id": course_id,
            "completed": True
        })
        
        # Buscar enrollment
        enrollment = await enrollments_col.find_one({
            "user_id": user_id,
            "course_id": course_id
        })
        
        if enrollment:
            total = enrollment.get("total_lessons", 1) or 1
            progress_percent = (completed_count / total) * 100
            
            update_data = {
                "lessons_completed": completed_count,
                "progress_percent": round(progress_percent, 1),
                "last_activity_at": datetime.utcnow(),
            }
            
            # Se completou 100%
            if progress_percent >= 100:
                update_data["completed_at"] = datetime.utcnow()
            
            await enrollments_col.update_one(
                {"_id": enrollment["_id"]},
                {"$set": update_data}
            )
    
    @classmethod
    async def get_lesson_progress(cls, user_id: str, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Busca progresso de um usu?rio em uma aula espec?fica."""
        collection = cls._get_progress_collection()
        
        progress = await collection.find_one({
            "user_id": user_id,
            "lesson_id": lesson_id
        })
        
        return progress
    
    @classmethod
    def _serialize_enrollment(cls, enrollment: Dict[str, Any]) -> Dict[str, Any]:
        """Serializa documento de matr?cula."""
        if not enrollment:
            return None
        doc = dict(enrollment)
        doc["id"] = str(doc.pop("_id"))
        return doc

    # ==================== QUIZ ====================

    QUIZZES_COLLECTION = "quizzes"
    QUIZ_ATTEMPTS_COLLECTION = "quiz_attempts"
    CERTIFICATES_COLLECTION = "certificates"

    @classmethod
    def _get_quizzes_collection(cls):
        db = get_db()
        return db[cls.QUIZZES_COLLECTION]

    @classmethod
    def _get_quiz_attempts_collection(cls):
        db = get_db()
        return db[cls.QUIZ_ATTEMPTS_COLLECTION]

    @classmethod
    def _get_certificates_collection(cls):
        db = get_db()
        return db[cls.CERTIFICATES_COLLECTION]

    @classmethod
    async def create_quiz(cls, quiz_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cria um quiz para uma aula."""
        collection = cls._get_quizzes_collection()
        now = datetime.utcnow()
        quiz_doc = {**quiz_data, "created_at": now, "updated_at": now}
        result = await collection.insert_one(quiz_doc)
        quiz_doc["_id"] = result.inserted_id
        return cls._serialize_doc(quiz_doc)

    @classmethod
    async def get_quiz_by_lesson(cls, lesson_id: str) -> Optional[Dict[str, Any]]:
        """Busca quiz associado a uma aula."""
        collection = cls._get_quizzes_collection()
        quiz = await collection.find_one({"lesson_id": lesson_id})
        return cls._serialize_doc(quiz) if quiz else None

    @classmethod
    async def record_quiz_attempt(
        cls,
        user_id: str,
        quiz_id: str,
        lesson_id: str,
        course_id: str,
        answers: List[int],
        score: float,
        passed: bool,
    ) -> Dict[str, Any]:
        """Registra uma tentativa de quiz."""
        collection = cls._get_quiz_attempts_collection()
        attempt_doc = {
            "user_id": user_id,
            "quiz_id": quiz_id,
            "lesson_id": lesson_id,
            "course_id": course_id,
            "answers": answers,
            "score": score,
            "passed": passed,
            "attempted_at": datetime.utcnow(),
        }
        result = await collection.insert_one(attempt_doc)
        attempt_doc["_id"] = result.inserted_id
        return cls._serialize_doc(attempt_doc)

    @classmethod
    async def get_latest_quiz_attempt(
        cls, user_id: str, quiz_id: str
    ) -> Optional[Dict[str, Any]]:
        """Busca a tentativa mais recente de um quiz por um usuário."""
        collection = cls._get_quiz_attempts_collection()
        attempt = await collection.find_one(
            {"user_id": user_id, "quiz_id": quiz_id},
            sort=[("attempted_at", -1)],
        )
        return cls._serialize_doc(attempt) if attempt else None

    # ==================== CERTIFICATES ====================

    @classmethod
    async def issue_certificate(
        cls,
        user_id: str,
        course_id: str,
        course_title: str,
        user_name: str,
        cert_hash: str,
    ) -> Dict[str, Any]:
        """Emite um certificado (ou retorna o existente)."""
        collection = cls._get_certificates_collection()
        enrollments_col = cls._get_enrollments_collection()

        existing = await collection.find_one({"user_id": user_id, "course_id": course_id})
        if existing:
            return cls._serialize_doc(existing)

        now = datetime.utcnow()
        cert_doc = {
            "user_id": user_id,
            "course_id": course_id,
            "course_title": course_title,
            "user_name": user_name,
            "issued_at": now,
            "cert_hash": cert_hash,
        }
        result = await collection.insert_one(cert_doc)
        cert_doc["_id"] = result.inserted_id

        # Mark enrollment as certificate issued
        await enrollments_col.update_one(
            {"user_id": user_id, "course_id": course_id},
            {"$set": {"certificate_issued": True}},
        )

        return cls._serialize_doc(cert_doc)

    @classmethod
    async def get_certificate(
        cls, user_id: str, course_id: str
    ) -> Optional[Dict[str, Any]]:
        """Busca certificado do usuário para um curso."""
        collection = cls._get_certificates_collection()
        cert = await collection.find_one({"user_id": user_id, "course_id": course_id})
        return cls._serialize_doc(cert) if cert else None

    @classmethod
    async def get_course_progress(
        cls, user_id: str, course_id: str
    ) -> Optional[Dict[str, Any]]:
        """Alias: retorna enrollment (contém dados de progresso)."""
        return await cls.get_user_enrollment(user_id, course_id)

    @classmethod
    def _serialize_doc(cls, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Serializa documento genérico (converte _id → id)."""
        if not doc:
            return None
        result = dict(doc)
        result["id"] = str(result.pop("_id"))
        return result
