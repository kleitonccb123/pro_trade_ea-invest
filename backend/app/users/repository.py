"""
User Repository - MongoDB Implementation with Motor

This module provides async database operations for User documents.
Uses the global MongoDB connection from app.core.database.

Collections:
- users: Main user documents
- user_sessions: Active login sessions (optional)

Author: Crypto Trade Hub
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from bson import ObjectId

from app.core.database import get_db
from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for User CRUD operations in MongoDB.
    
    All methods are async and use the global database connection.
    """
    
    COLLECTION_NAME = "users"
    
    @classmethod
    def _get_collection(cls):
        """Get the users collection from database."""
        db = get_db()
        return db[cls.COLLECTION_NAME]
    
    # ==================== CREATE ====================
    
    @classmethod
    async def create(
        cls,
        email: str,
        password: str,
        name: str = None,
        auth_provider: str = "local",
        google_id: str = None,
        **extra_fields
    ) -> Dict[str, Any]:
        """
        Create a new user in the database.
        
        Args:
            email: User's email (unique)
            password: Plain text password (will be hashed)
            name: Display name
            auth_provider: 'local', 'google', etc.
            google_id: Google OAuth ID if using Google login
            extra_fields: Additional fields to store
            
        Returns:
            Created user document
            
        Raises:
            ValueError: If email already exists
        """
        collection = cls._get_collection()
        
        # Check if email already exists
        existing = await collection.find_one({"email": email.lower()})
        if existing:
            raise ValueError(f"Email already registered: {email}")
        
        # Prepare user document
        now = datetime.utcnow()
        user_doc = {
            "email": email.lower(),
            "hashed_password": get_password_hash(password) if password else None,
            "name": name or email.split("@")[0],
            "username": email.split("@")[0],
            "full_name": name or email.split("@")[0],
            "auth_provider": auth_provider,
            "google_id": google_id,
            "is_active": True,
            "is_superuser": False,
            "created_at": now,
            "updated_at": now,
            "last_login": None,
            "login_count": 0,
            **extra_fields
        }
        
        # Insert into database
        result = await collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        
        logger.info(f"? Created user: {email}")
        return user_doc
    
    # ==================== READ ====================
    
    @classmethod
    async def find_by_id(cls, user_id: str | ObjectId) -> Optional[Dict[str, Any]]:
        """Find user by ID."""
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except Exception:
                return None
        
        return await collection.find_one({"_id": user_id})
    
    @classmethod
    async def find_by_email(cls, email: str) -> Optional[Dict[str, Any]]:
        """Find user by email (case-insensitive)."""
        collection = cls._get_collection()
        return await collection.find_one({"email": email.lower()})
    
    @classmethod
    async def find_by_google_id(cls, google_id: str) -> Optional[Dict[str, Any]]:
        """Find user by Google OAuth ID."""
        collection = cls._get_collection()
        return await collection.find_one({"google_id": google_id})
    
    @classmethod
    async def find_all(
        cls,
        skip: int = 0,
        limit: int = 100,
        filter_dict: Dict = None
    ) -> List[Dict[str, Any]]:
        """
        Find all users with pagination.
        
        Args:
            skip: Number of documents to skip
            limit: Maximum documents to return
            filter_dict: Optional MongoDB filter
            
        Returns:
            List of user documents
        """
        collection = cls._get_collection()
        query = filter_dict or {}
        
        cursor = collection.find(query).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    @classmethod
    async def count(cls, filter_dict: Dict = None) -> int:
        """Count users matching filter."""
        collection = cls._get_collection()
        return await collection.count_documents(filter_dict or {})
    
    # ==================== UPDATE ====================
    
    @classmethod
    async def update(
        cls,
        user_id: str | ObjectId,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update user by ID.
        
        Args:
            user_id: User's ObjectId
            updates: Fields to update
            
        Returns:
            Updated user document or None
        """
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # Add updated_at timestamp
        updates["updated_at"] = datetime.utcnow()
        
        result = await collection.find_one_and_update(
            {"_id": user_id},
            {"$set": updates},
            return_document=True
        )
        
        if result:
            logger.info(f"? Updated user: {user_id}")
        
        return result
    
    @classmethod
    async def update_password(
        cls,
        user_id: str | ObjectId,
        new_password: str
    ) -> bool:
        """Update user's password."""
        result = await cls.update(
            user_id,
            {"hashed_password": get_password_hash(new_password)}
        )
        return result is not None
    
    @classmethod
    async def record_login(cls, user_id: str | ObjectId) -> None:
        """Record successful login timestamp."""
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        await collection.update_one(
            {"_id": user_id},
            {
                "$set": {"last_login": datetime.utcnow()},
                "$inc": {"login_count": 1}
            }
        )
    
    # ==================== DELETE ====================
    
    @classmethod
    async def delete(cls, user_id: str | ObjectId) -> bool:
        """Delete user by ID."""
        collection = cls._get_collection()
        
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        result = await collection.delete_one({"_id": user_id})
        
        if result.deleted_count > 0:
            logger.info(f"? Deleted user: {user_id}")
            return True
        return False
    
    # ==================== AUTHENTICATION ====================
    
    @classmethod
    async def authenticate(cls, email: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with email and password.
        
        Args:
            email: User's email
            password: Plain text password
            
        Returns:
            User document if authenticated, None otherwise
        """
        user = await cls.find_by_email(email)
        
        if not user:
            logger.warning(f"? User not found: {email}")
            return None
        
        if not user.get("hashed_password"):
            logger.warning(f"? User has no password (OAuth only): {email}")
            return None
        
        if not verify_password(password, user["hashed_password"]):
            logger.warning(f"? Invalid password for: {email}")
            return None
        
        if not user.get("is_active", True):
            logger.warning(f"? User is inactive: {email}")
            return None
        
        # Record login
        await cls.record_login(user["_id"])
        
        logger.info(f"? User authenticated: {email}")
        return user
    
    @classmethod
    async def create_or_update_google_user(
        cls,
        google_id: str,
        email: str,
        name: str = None,
        picture: str = None
    ) -> Dict[str, Any]:
        """
        Create or update user from Google OAuth.
        
        If user exists (by google_id or email), updates their info.
        Otherwise creates a new user.
        
        Returns:
            User document
        """
        collection = cls._get_collection()
        
        # Try to find by google_id first
        user = await cls.find_by_google_id(google_id)
        
        if not user:
            # Try by email
            user = await cls.find_by_email(email)
        
        if user:
            # Update existing user
            updates = {
                "google_id": google_id,
                "last_login": datetime.utcnow(),
                "auth_provider": "google",
            }
            if name:
                updates["name"] = name
                updates["full_name"] = name
            if picture:
                updates["picture"] = picture
            
            return await cls.update(user["_id"], updates)
        
        # Create new user
        return await cls.create(
            email=email,
            password=None,  # Google users don't have password
            name=name,
            auth_provider="google",
            google_id=google_id,
            picture=picture
        )
    
    # ==================== INDEXES ====================
    
    @classmethod
    async def ensure_indexes(cls) -> None:
        """Create necessary indexes for the users collection."""
        collection = cls._get_collection()
        
        try:
            # Unique index on email
            await collection.create_index("email", unique=True)
            
            # Index on google_id for OAuth lookups
            await collection.create_index("google_id", sparse=True)
            
            # Index on is_active for filtering
            await collection.create_index("is_active")
            
            logger.info(f"? Created indexes for {cls.COLLECTION_NAME}")
        except Exception as e:
            logger.warning(f"??  Could not create indexes: {e}")


# Convenience instance
user_repository = UserRepository()
