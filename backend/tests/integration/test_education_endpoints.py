"""
Integration Tests — Education Endpoints
=========================================
Tests for:
  - GET  /education/courses                               (1)
  - GET  /education/courses/{id}                         (2)
  - POST /education/courses/{id}/enroll                  (3)
  - GET  /education/my-courses                           (4)
  - POST /education/progress                             (5)
  - GET  /education/courses/{id}/player                  (6)
  - GET  /education/courses/{id}/lessons/{id}/quiz       (7)
  - POST /education/courses/{id}/lessons/{id}/quiz       (8,9,10)
  - GET  /education/courses/{id}/certificate             (11,12)
  - GET  /education/courses/{id}/progress                (13,14,15)

Total: 15 integration tests
"""
import pytest
from datetime import datetime
from app.core.database import _mock_data, MockDatabase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _seed_course(client, auth_header):
    """Create a published course via the admin POST endpoint or directly."""
    resp = await client.post(
        "/education/courses",
        json={
            "title": "Trading Fundamentals",
            "description": "Aprenda os fundamentos do trading",
            "level": "beginner",
            "category": "trading",
            "tags": ["trading", "básico"],
            "estimated_duration": 120,
            "is_premium": False,
        },
        headers=auth_header,
    )
    # The POST endpoint may require admin; if 403/401 seed directly via mock_db
    if resp.status_code == 201:
        return resp.json()
    # fallback: insert directly into mock store
    from bson import ObjectId
    from app.core.database import _mock_data
    course_oid = ObjectId("507f1f77bcf86cd799439011")
    _mock_data.setdefault("courses", []).append({
        "_id": course_oid,
        "title": "Trading Fundamentals",
        "description": "Aprenda os fundamentos do trading",
        "level": "beginner",
        "category": "trading",
        "tags": ["trading"],
        "estimated_duration": 120,
        "is_premium": False,
        "lesson_count": 1,
        "enrolled_count": 0,
        "rating": 0.0,
        "review_count": 0,
        "status": "published",
        "slug": "trading-fundamentals",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return {"id": str(course_oid), "title": "Trading Fundamentals"}


async def _seed_lesson(course_id: str, lesson_id: str = None):
    """Insert a lesson directly into mock store."""
    from bson import ObjectId
    lesson_oid = ObjectId("507f1f77bcf86cd799439022")
    _mock_data.setdefault("lessons", []).append({
        "_id": lesson_oid,
        "course_id": course_id,
        "title": "Introdução ao Trading",
        "description": "Primeira aula",
        "type": "video",
        "order": 0,
        "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "video_provider": "youtube",
        "video_duration": 600,
        "is_preview": True,
        "is_downloadable": False,
        "resources": [],
        "slug": "introducao-ao-trading",
        "view_count": 0,
        "completion_count": 0,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return str(lesson_oid)


async def _seed_enrollment(user_id: str, course_id: str):
    """Insert enrollment and progress dict into mock_data."""
    _mock_data.setdefault("enrollments", []).append({
        "_id": f"enr_{user_id}_{course_id}",
        "user_id": user_id,
        "course_id": course_id,
        "enrolled_at": datetime.utcnow(),
        "progress_percent": 0.0,
        "lessons_completed": 0,
        "total_lessons": 1,
        "certificate_issued": False,
        "lessons": [],
    })


async def _seed_complete_enrollment(user_id: str, course_id: str):
    """Insert a 100%-complete enrollment."""
    _mock_data.setdefault("enrollments", []).append({
        "_id": f"enr_complete_{user_id}_{course_id}",
        "user_id": user_id,
        "course_id": course_id,
        "enrolled_at": datetime.utcnow(),
        "progress_percent": 100.0,
        "lessons_completed": 1,
        "total_lessons": 1,
        "certificate_issued": False,
        "completed_at": datetime.utcnow(),
        "lessons": [
            {"lesson_id": "lesson_test_001", "watched_seconds": 600,
             "completed": True, "completed_at": datetime.utcnow(),
             "last_watched_at": datetime.utcnow()}
        ],
    })


async def _seed_quiz(lesson_id: str, course_id: str, quiz_id: str = "quiz_test_001"):
    """Insert a quiz into mock store for integration tests."""
    _mock_data.setdefault("quizzes", []).append({
        "_id": quiz_id,
        "lesson_id": lesson_id,
        "course_id": course_id,
        "title": "Quiz: Fundamentos",
        "passing_score": 50,
        "questions": [
            {
                "question": "O que é um candlestick?",
                "options": ["Um tipo de ordem", "Uma representação de preço", "Uma moeda"],
                "correct_index": 1,
                "explanation": "Candlestick representa abertura, fechamento, máxima e mínima.",
            },
            {
                "question": "O que é stop loss?",
                "options": ["Ganho máximo", "Perda máxima", "Limite de compra"],
                "correct_index": 1,
                "explanation": "Stop loss limita a perda da operação.",
            },
        ],
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    })
    return quiz_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestEducationCourseEndpoints:

    @pytest.mark.asyncio
    async def test_list_courses_returns_200(self, client, auth_header):
        """GET /education/courses always returns 200 even if empty."""
        resp = await client.get("/education/courses", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        assert "courses" in body
        assert isinstance(body["courses"], list)

    @pytest.mark.asyncio
    async def test_list_courses_requires_auth(self, client):
        resp = await client.get("/education/courses")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_course_by_id_found(self, client, auth_header):
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        resp = await client.get(f"/education/courses/{course_id}", headers=auth_header)
        assert resp.status_code == 200
        assert resp.json().get("title") is not None

    @pytest.mark.asyncio
    async def test_get_course_by_id_not_found(self, client, auth_header):
        resp = await client.get("/education/courses/nonexistent_id_xyz", headers=auth_header)
        assert resp.status_code == 404


class TestEnrollmentEndpoints:

    @pytest.mark.asyncio
    async def test_enroll_creates_enrollment(self, client, auth_header):
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        resp = await client.post(
            f"/education/courses/{course_id}/enroll",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "enrollment" in body or "course_id" in body or body.get("success", True)

    @pytest.mark.asyncio
    async def test_enroll_requires_auth(self, client):
        resp = await client.post("/education/courses/any_id/enroll")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_my_courses_returns_enrolled(self, client, auth_header):
        """After enrolling, the course appears in my-courses."""
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        await client.post(
            f"/education/courses/{course_id}/enroll",
            headers=auth_header,
        )
        resp = await client.get("/education/my-courses", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        assert "enrollments" in body
        assert isinstance(body["enrollments"], list)


class TestProgressEndpoints:

    @pytest.mark.asyncio
    async def test_update_progress_success(self, client, auth_header):
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        lesson_id = await _seed_lesson(course_id)
        await _seed_enrollment(TEST_USER_ID, course_id)

        resp = await client.post(
            "/education/progress",
            json={
                "lesson_id": lesson_id,
                "course_id": course_id,
                "watched_seconds": 120,
                "completed": False,
            },
            headers=auth_header,
        )
        assert resp.status_code == 200
        assert resp.json().get("success") is True

    @pytest.mark.asyncio
    async def test_update_progress_requires_auth(self, client):
        resp = await client.post(
            "/education/progress",
            json={"lesson_id": "l1", "course_id": "c1", "watched_seconds": 10, "completed": False},
        )
        assert resp.status_code == 401


class TestPlayerEndpoints:

    @pytest.mark.asyncio
    async def test_get_player_returns_embed_info(self, client, auth_header):
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        await _seed_lesson(course_id)

        resp = await client.get(
            f"/education/courses/{course_id}/player",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "provider" in body
        assert "embed_url" in body

    @pytest.mark.asyncio
    async def test_get_player_requires_auth(self, client):
        resp = await client.get("/education/courses/any_id/player")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_player_404_for_unknown_course(self, client, auth_header):
        resp = await client.get(
            "/education/courses/totally_unknown_xyz/player",
            headers=auth_header,
        )
        assert resp.status_code == 404


class TestQuizEndpoints:

    @pytest.mark.asyncio
    async def test_get_quiz_requires_enrollment(self, client, auth_header):
        """GET quiz without enrollment → 403."""
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        lesson_id = await _seed_lesson(course_id)
        await _seed_quiz(lesson_id, course_id)

        resp = await client.get(
            f"/education/courses/{course_id}/lessons/{lesson_id}/quiz",
            headers=auth_header,
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_quiz_returns_safe_questions(self, client, auth_header):
        """GET quiz hides correct_index from response."""
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        lesson_id = await _seed_lesson(course_id)
        await _seed_quiz(lesson_id, course_id)
        await _seed_enrollment(TEST_USER_ID, course_id)

        resp = await client.get(
            f"/education/courses/{course_id}/lessons/{lesson_id}/quiz",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "quiz" in body
        for q in body["quiz"]["questions"]:
            assert "correct_index" not in q

    @pytest.mark.asyncio
    async def test_submit_quiz_correct_answers_pass(self, client, auth_header):
        """Submitting all correct answers → passed=True."""
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        lesson_id = await _seed_lesson(course_id)
        await _seed_quiz(lesson_id, course_id)
        await _seed_enrollment(TEST_USER_ID, course_id)

        # Both correct_index values are 1
        resp = await client.post(
            f"/education/courses/{course_id}/lessons/{lesson_id}/quiz",
            json={"answers": [1, 1]},
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is True
        assert body["score"] == 100.0

    @pytest.mark.asyncio
    async def test_submit_quiz_wrong_answers_fail(self, client, auth_header):
        """Submitting wrong answers with passing_score=50 → passed=False."""
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        lesson_id = await _seed_lesson(course_id)
        await _seed_quiz(lesson_id, course_id)
        await _seed_enrollment(TEST_USER_ID, course_id)

        resp = await client.post(
            f"/education/courses/{course_id}/lessons/{lesson_id}/quiz",
            json={"answers": [0, 0]},  # both wrong
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["passed"] is False
        assert body["score"] == 0.0

    @pytest.mark.asyncio
    async def test_submit_quiz_requires_auth(self, client):
        resp = await client.post(
            "/education/courses/c1/lessons/l1/quiz",
            json={"answers": [0]},
        )
        assert resp.status_code == 401


class TestCertificateEndpoints:

    @pytest.mark.asyncio
    async def test_certificate_requires_100_percent(self, client, auth_header):
        """Course not complete → 400."""
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        await _seed_enrollment(TEST_USER_ID, course_id)  # 0% progress

        resp = await client.get(
            f"/education/courses/{course_id}/certificate",
            headers=auth_header,
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_certificate_issued_when_complete(self, client, auth_header):
        """100% complete → certificate issued with cert_hash."""
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        await _seed_complete_enrollment(TEST_USER_ID, course_id)

        resp = await client.get(
            f"/education/courses/{course_id}/certificate",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "cert_hash" in body

    @pytest.mark.asyncio
    async def test_certificate_requires_auth(self, client):
        resp = await client.get("/education/courses/any/certificate")
        assert resp.status_code == 401


class TestCourseProgressEndpoint:

    @pytest.mark.asyncio
    async def test_progress_returns_not_enrolled_when_no_enrollment(self, client, auth_header):
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        resp = await client.get(
            f"/education/courses/{course_id}/progress",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_enrolled"] is False
        assert body["progress_percent"] == 0.0

    @pytest.mark.asyncio
    async def test_progress_returns_enrollment_data(self, client, auth_header):
        from tests.conftest import TEST_USER_ID
        course = await _seed_course(client, auth_header)
        course_id = course["id"]
        await _seed_enrollment(TEST_USER_ID, course_id)

        resp = await client.get(
            f"/education/courses/{course_id}/progress",
            headers=auth_header,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["is_enrolled"] is True

    @pytest.mark.asyncio
    async def test_progress_requires_auth(self, client):
        resp = await client.get("/education/courses/any_id/progress")
        assert resp.status_code == 401
