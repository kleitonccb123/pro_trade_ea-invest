import hashlib
import bcrypt

# N?mero de rounds para bcrypt
BCRYPT_ROUNDS = 12


def _prepare_password(password: str) -> bytes:
    """
    Prepare password for bcrypt by hashing with SHA256.
    This ensures:
    1. Password is always under 72 bytes (bcrypt limit)
    2. All passwords are normalized to same length (64 hex chars)
    Returns bytes ready for bcrypt.
    """
    # Ensure password is a string
    if not isinstance(password, str):
        password = str(password)
    
    # Truncate extremely long passwords to prevent DoS
    max_password_length = 1024
    if len(password) > max_password_length:
        password = password[:max_password_length]
    
    # SHA256 hash produces 64 hex characters (always under 72 bytes)
    sha_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    return sha_hash.encode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password"""
    try:
        prepared = _prepare_password(plain_password)
        # Ensure hashed_password is bytes
        if isinstance(hashed_password, str):
            hashed_password = hashed_password.encode('utf-8')
        return bcrypt.checkpw(prepared, hashed_password)
    except Exception as e:
        print(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt (with SHA256 pre-processing)"""
    try:
        prepared = _prepare_password(password)
        salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        hashed = bcrypt.hashpw(prepared, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        print(f"Password hashing error: {e}")
        raise ValueError(f"Erro ao processar senha: {str(e)}")


def get_current_user(db=None):
    """Dependency to get current authenticated user"""
    # For now, return a dummy user object since auth implementation may vary
    # This can be replaced with actual JWT/token validation
    return {"id": 1, "email": "user@example.com"}
