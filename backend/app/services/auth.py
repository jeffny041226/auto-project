"""Authentication service."""
import uuid
from datetime import datetime, timedelta
from typing import Optional

from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, TokenResponse
from app.utils.logger import get_logger

logger = get_logger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """Authentication service for user management and JWT."""

    def __init__(self, db: AsyncSession):
        """Initialize auth service."""
        self.db = db

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + (
            expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> Optional[dict]:
        """Decode and validate JWT token."""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            return payload
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    async def register(self, user_data: UserCreate) -> UserResponse:
        """Register a new user."""
        # Check if username exists
        result = await self.db.execute(
            select(User).where(User.username == user_data.username)
        )
        if result.scalar_one_or_none():
            raise ValueError(f"Username '{user_data.username}' already exists")

        # Create user
        user = User(
            user_id=str(uuid.uuid4()),
            username=user_data.username,
            password_hash=self.hash_password(user_data.password),
            email=user_data.email,
            role="user",
            status="active",
        )

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        logger.info(f"User registered: {user.username}")
        return UserResponse.model_validate(user)

    async def login(self, credentials: UserLogin) -> Optional[TokenResponse]:
        """Authenticate user and return tokens."""
        result = await self.db.execute(
            select(User).where(User.username == credentials.username)
        )
        user = result.scalar_one_or_none()

        if not user or not self.verify_password(credentials.password, user.password_hash):
            logger.warning(f"Failed login attempt for username: {credentials.username}")
            return None

        if user.status != "active":
            logger.warning(f"Login attempt for inactive user: {credentials.username}")
            return None

        # Create tokens
        token_data = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
        }
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)

        logger.info(f"User logged in: {user.username}")
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
        )

    async def refresh_token(self, refresh_token: str) -> Optional[TokenResponse]:
        """Refresh access token using refresh token."""
        payload = self.decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            return None

        # Verify user still exists and is active
        user_id = payload.get("sub")
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        user = result.scalar_one_or_none()

        if not user or user.status != "active":
            return None

        # Create new tokens
        token_data = {
            "sub": user.user_id,
            "username": user.username,
            "role": user.role,
        }
        access_token = self.create_access_token(token_data)
        new_refresh_token = self.create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
        )

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by user_id."""
        result = await self.db.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()
