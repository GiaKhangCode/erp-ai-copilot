import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import jwt, JWTError
from app.core.config import settings

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    # Truncate to 72 bytes if necessary per bcrypt spec
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def hash_token(token: str) -> str:
    """Băm token (refresh token) bằng SHA-256 để lưu trữ an toàn trong CSDL."""
    import hashlib
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_refresh_token(data: dict, expires_days: int = 7) -> tuple[str, str, datetime]:
    """
    Tạo Refresh Token (JWT dài hạn).
    Trả về: (raw_refresh_token, sha256_hash, expires_at_utc)
    Bổ sung claim jti ngẫu nhiên để đảm bảo tính duy nhất tuyệt đối.
    """
    import uuid
    to_encode = data.copy()
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)
    to_encode.update({
        "jti": str(uuid.uuid4()),
        "exp": expires_at,
        "type": "refresh",
    })
    raw_token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash, expires_at


