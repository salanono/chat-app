# backend/app/auth.py
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import AsyncSessionLocal
from . import models

# ==== JWT 設定 ====
SECRET_KEY = "CHANGE_ME_TO_SOMETHING_SECURE"  # 本番では環境変数などで
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalars().first()


async def authenticate_user(email: str, password: str, db: AsyncSession) -> Optional[models.User]:
    user = await get_user_by_email(db, email)
    if not user:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    async with AsyncSessionLocal() as db:
        user = await get_user_by_email(db, email)
        if user is None:
            raise credentials_exception
        return user


async def ensure_default_admin():
    """
    アプリ起動時にデフォルトの会社 & 管理者ユーザーが無ければ作る。
    - Company.name = 'Default Company'
    - admin user: admin@example.com / admin123
    """
    async with AsyncSessionLocal() as db:
        # 既に何か会社があれば何もしない（適当に 1 件取る）
        result_company = await db.execute(select(models.Company))
        company = result_company.scalars().first()
        if not company:
            company = models.Company(name="Default Company")
            db.add(company)
            await db.flush()  # company.id を確定させる

        # admin ユーザーが存在するか
        result_user = await db.execute(
            select(models.User).where(models.User.email == "admin@example.com")
        )
        admin = result_user.scalars().first()
        if not admin:
            admin = models.User(
                email="admin@example.com",
                password_hash=get_password_hash("admin123"),
                display_name="Admin",
                role=models.UserRole.ADMIN,
                company=company,
            )
            db.add(admin)

        await db.commit()