"""
Centralized helper for extracting a user ID from various current_user formats.

The system persists users in both SQLite (UUID string in "id" key) and MongoDB
(ObjectId in "_id" key).  This function normalises both into a plain str.
"""
from fastapi import HTTPException


def get_user_id(current_user: dict) -> str:
    """Return the user's ID as a str, regardless of storage backend.

    Supports:
    - SQLite-backed users: {"id": "uuid-string", ...}
    - MongoDB-backed users: {"_id": ObjectId(...), ...}
    - SimpleNamespace objects with an .id attribute

    Raises HTTPException 401 if no ID can be found (misconfigured token).
    """
    uid = (
        current_user.get("id")
        or current_user.get("_id")
        or getattr(current_user, "id", None)
    ) if isinstance(current_user, dict) else getattr(current_user, "id", None)

    if not uid:
        raise HTTPException(status_code=401, detail="Usuário sem ID válido")
    return str(uid)
