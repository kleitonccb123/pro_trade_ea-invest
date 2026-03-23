"""
Unit Tests — Education Service
================================
Tests for:
  - extract_video_embed  (8 tests)
  - score_quiz_attempt   (5 tests)
  - generate_certificate_hash (3 tests)
  - EducationRepository  in-memory (11 tests via MockDatabase)

Total: 27 unit tests
"""
import re
import pytest
from datetime import datetime
from unittest.mock import patch

from app.education.service import (
    extract_video_embed,
    score_quiz_attempt,
    generate_certificate_hash,
)
from app.education.repository import EducationRepository


# ===========================================================================
# Helpers
# ===========================================================================

def _patch_db(mock_db):
    """Context-manager that routes every get_db() call to mock_db."""
    return patch("app.education.repository.get_db", return_value=mock_db)


# ===========================================================================
# TestExtractVideoEmbed
# ===========================================================================

class TestExtractVideoEmbed:
    def test_youtube_watch_url(self):
        r = extract_video_embed("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert r["provider"] == "youtube"
        assert r["video_id"] == "dQw4w9WgXcQ"
        assert "youtube.com/embed/dQw4w9WgXcQ" in r["embed_url"]

    def test_youtube_short_url(self):
        r = extract_video_embed("https://youtu.be/dQw4w9WgXcQ")
        assert r["provider"] == "youtube"
        assert r["video_id"] == "dQw4w9WgXcQ"
        assert "youtube.com/embed/" in r["embed_url"]

    def test_youtube_embed_passthrough(self):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        r = extract_video_embed(url)
        assert r["provider"] == "youtube"
        assert r["embed_url"] == url

    def test_vimeo_url(self):
        r = extract_video_embed("https://vimeo.com/123456789")
        assert r["provider"] == "vimeo"
        assert r["video_id"] == "123456789"
        assert "player.vimeo.com/video/123456789" in r["embed_url"]

    def test_vimeo_player_passthrough(self):
        url = "https://player.vimeo.com/video/987654321"
        r = extract_video_embed(url)
        assert r["provider"] == "vimeo"
        assert r["embed_url"] == url

    def test_direct_video_url(self):
        r = extract_video_embed("https://cdn.example.com/lesson.mp4")
        assert r["provider"] == "direct"
        assert r["embed_url"] == "https://cdn.example.com/lesson.mp4"

    def test_empty_string(self):
        r = extract_video_embed("")
        assert r["provider"] == "direct"
        assert r["embed_url"] == ""

    def test_none_url(self):
        r = extract_video_embed(None)
        assert r["provider"] == "direct"
        assert r["embed_url"] == ""


# ===========================================================================
# TestScoreQuizAttempt
# ===========================================================================

class TestScoreQuizAttempt:
    QUESTIONS = [
        {"question": "Q1", "options": ["A", "B", "C"], "correct_index": 0},
        {"question": "Q2", "options": ["A", "B", "C"], "correct_index": 2},
        {"question": "Q3", "options": ["A", "B", "C"], "correct_index": 1},
        {"question": "Q4", "options": ["A", "B", "C"], "correct_index": 0},
    ]

    def test_all_correct(self):
        score, correct = score_quiz_attempt(self.QUESTIONS, [0, 2, 1, 0])
        assert score == 100.0
        assert correct == 4

    def test_all_wrong(self):
        score, correct = score_quiz_attempt(self.QUESTIONS, [1, 0, 0, 1])
        assert score == 0.0
        assert correct == 0

    def test_partial_score_50(self):
        # 2 out of 4 correct
        score, correct = score_quiz_attempt(self.QUESTIONS, [0, 2, 0, 1])
        assert correct == 2
        assert score == 50.0

    def test_empty_questions(self):
        score, correct = score_quiz_attempt([], [])
        assert score == 0.0
        assert correct == 0

    def test_fewer_answers_than_questions(self):
        """Missing answers are treated as wrong."""
        score, correct = score_quiz_attempt(self.QUESTIONS, [0])  # 1 of 4
        assert correct == 1
        assert score == 25.0


# ===========================================================================
# TestGenerateCertificateHash
# ===========================================================================

class TestGenerateCertificateHash:
    def test_returns_32_char_hex(self):
        h = generate_certificate_hash("user1", "course1", datetime.utcnow())
        assert len(h) == 32
        assert re.fullmatch(r"[0-9a-f]{32}", h)

    def test_unique_per_call(self):
        """Nonce in implementation ensures different hashes for same inputs."""
        ts = datetime(2026, 3, 11, 12, 0, 0)
        h1 = generate_certificate_hash("u1", "c1", ts)
        h2 = generate_certificate_hash("u1", "c1", ts)
        assert h1 != h2  # random nonce guarantees uniqueness

    def test_is_string(self):
        h = generate_certificate_hash("x", "y", datetime.utcnow())
        assert isinstance(h, str)


# ===========================================================================
# TestEducationRepositoryInMemory
# ===========================================================================

class TestEducationRepositoryInMemory:
    """Exercises EducationRepository against MockDatabase."""

    # ---- Course CRUD ----

    @pytest.mark.asyncio
    async def test_create_course_sets_id(self, mock_db):
        with _patch_db(mock_db):
            course = await EducationRepository.create_course({
                "title": "Curso Teste",
                "description": "desc",
                "level": "beginner",
                "category": "trading",
                "tags": [],
                "estimated_duration": 60,
                "is_premium": False,
                "lesson_count": 0,
                "enrolled_count": 0,
                "rating": 0.0,
                "review_count": 0,
                "status": "published",
            })
        assert course["id"] is not None
        assert course["title"] == "Curso Teste"

    @pytest.mark.asyncio
    async def test_get_course_by_id_returns_correct(self, mock_db):
        with _patch_db(mock_db):
            created = await EducationRepository.create_course({
                "title": "Recuperar Curso",
                "description": "d",
                "level": "beginner",
                "category": "trading",
                "tags": [],
                "estimated_duration": 30,
                "is_premium": False,
                "lesson_count": 0,
                "enrolled_count": 0,
                "rating": 0.0,
                "review_count": 0,
                "status": "published",
            })
            fetched = await EducationRepository.get_course_by_id(created["id"])
        assert fetched is not None
        assert fetched["title"] == "Recuperar Curso"

    @pytest.mark.asyncio
    async def test_list_courses_returns_published(self, mock_db):
        with _patch_db(mock_db):
            await EducationRepository.create_course({
                "title": "Pub",
                "description": "d",
                "level": "beginner",
                "category": "trading",
                "tags": [],
                "estimated_duration": 30,
                "is_premium": False,
                "lesson_count": 0,
                "enrolled_count": 0,
                "rating": 0.0,
                "review_count": 0,
                "status": "published",
            })
            result = await EducationRepository.list_courses(status="published")
        # list_courses returns a list of course dicts
        assert isinstance(result, list)
        assert len(result) >= 1

    # ---- Enrollment ----

    @pytest.mark.asyncio
    async def test_enroll_user_creates_enrollment(self, mock_db):
        with _patch_db(mock_db):
            course = await EducationRepository.create_course({
                "title": "Enroll Curso",
                "description": "d",
                "level": "beginner",
                "category": "trading",
                "tags": [],
                "estimated_duration": 60,
                "is_premium": False,
                "lesson_count": 2,
                "enrolled_count": 0,
                "rating": 0.0,
                "review_count": 0,
                "status": "published",
            })
            enrollment = await EducationRepository.enroll_user("u1", course["id"])
        assert enrollment["user_id"] == "u1"
        assert enrollment["course_id"] == course["id"]
        assert enrollment.get("progress_percent", 0) == 0.0

    @pytest.mark.asyncio
    async def test_enroll_twice_is_idempotent(self, mock_db):
        with _patch_db(mock_db):
            course = await EducationRepository.create_course({
                "title": "Idem Curso",
                "description": "d",
                "level": "beginner",
                "category": "trading",
                "tags": [],
                "estimated_duration": 30,
                "is_premium": False,
                "lesson_count": 0,
                "enrolled_count": 0,
                "rating": 0.0,
                "review_count": 0,
                "status": "published",
            })
            e1 = await EducationRepository.enroll_user("u2", course["id"])
            e2 = await EducationRepository.enroll_user("u2", course["id"])
        assert e1["id"] == e2["id"]

    # ---- Quiz ----

    @pytest.mark.asyncio
    async def test_create_and_get_quiz(self, mock_db):
        with _patch_db(mock_db):
            quiz = await EducationRepository.create_quiz({
                "lesson_id": "lesson1",
                "course_id": "course1",
                "title": "Quiz Básico",
                "passing_score": 70,
                "questions": [
                    {"question": "2+2?", "options": ["3", "4", "5"], "correct_index": 1}
                ],
            })
            fetched = await EducationRepository.get_quiz_by_lesson("lesson1")
        assert fetched is not None
        assert fetched["lesson_id"] == "lesson1"
        assert quiz["title"] == "Quiz Básico"

    @pytest.mark.asyncio
    async def test_get_quiz_returns_none_for_missing(self, mock_db):
        with _patch_db(mock_db):
            result = await EducationRepository.get_quiz_by_lesson("nonexistent_lesson")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_quiz_attempt_stores_data(self, mock_db):
        with _patch_db(mock_db):
            attempt = await EducationRepository.record_quiz_attempt(
                user_id="u1",
                quiz_id="q1",
                lesson_id="l1",
                course_id="c1",
                answers=[0, 1, 2],
                score=66.7,
                passed=False,
            )
        assert attempt["user_id"] == "u1"
        assert attempt["score"] == 66.7
        assert attempt["passed"] is False

    @pytest.mark.asyncio
    async def test_get_latest_quiz_attempt(self, mock_db):
        """record_quiz_attempt stores data that can be retrieved from the collection."""
        with _patch_db(mock_db):
            attempt = await EducationRepository.record_quiz_attempt(
                user_id="u3",
                quiz_id="qz",
                lesson_id="l3",
                course_id="c3",
                answers=[1],
                score=100.0,
                passed=True,
            )
            # Verify the attempt was stored (check via direct collection access)
            stored = await mock_db.quiz_attempts.find_one(
                {"user_id": "u3", "quiz_id": "qz"}
            )
        assert stored is not None
        assert stored["passed"] is True
        assert stored["score"] == 100.0

    # ---- Certificate ----

    @pytest.mark.asyncio
    async def test_issue_certificate_creates_record(self, mock_db):
        with _patch_db(mock_db):
            # seed enrollment so update_one has a doc to patch
            await mock_db.enrollments.insert_one({
                "user_id": "u10", "course_id": "c10", "certificate_issued": False
            })
            cert = await EducationRepository.issue_certificate(
                user_id="u10",
                course_id="c10",
                course_title="Avançado",
                user_name="Maria",
                cert_hash="deadbeef",
            )
        assert cert["cert_hash"] == "deadbeef"
        assert cert["user_name"] == "Maria"

    @pytest.mark.asyncio
    async def test_issue_certificate_is_idempotent(self, mock_db):
        """Calling issue_certificate twice returns the first certificate."""
        with _patch_db(mock_db):
            await mock_db.enrollments.insert_one({
                "user_id": "u20", "course_id": "c20", "certificate_issued": False
            })
            c1 = await EducationRepository.issue_certificate(
                user_id="u20", course_id="c20",
                course_title="Curso", user_name="João", cert_hash="hash1",
            )
            c2 = await EducationRepository.issue_certificate(
                user_id="u20", course_id="c20",
                course_title="Curso", user_name="João", cert_hash="hash2",
            )
        assert c1["cert_hash"] == c2["cert_hash"] == "hash1"
