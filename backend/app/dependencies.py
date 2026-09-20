import uuid
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.config import Settings
from app.database import get_db
from app.models.user import User
from app.services.storage import DatasetStorageService
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

_settings = Settings.from_ini()


def get_settings() -> Settings:
    return _settings


def get_storage_service() -> DatasetStorageService:
    return DatasetStorageService(storage_root=_settings.file_storage_path)


# TODO: Replace this with proper authentication mechanism (JWT/OAuth) in the future.
async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    x_user_email: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the development user from the request header.

    This is an intentionally temporary identity mechanism. Replace the header
    lookup with JWT/OAuth verification without changing route signatures.
    """
    if _settings.app_env != "dev":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Authentication is not configured for this environment",
        )

    email = x_user_email.strip().lower() if x_user_email else ""
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-User-Email header is required",
        )

    result = await db.exec(select(User).where(User.email == email))
    user = result.one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user",
        )

    return user


def get_model() -> BaseChatModel:
    if _settings.model and _settings.api_key and _settings.api_base_url:
        return ChatOpenAI(
            model=_settings.model,
            api_key=_settings.api_key,
            base_url=_settings.api_base_url,
            reasoning_effort=_settings.reasoning_effort or None,
            default_headers={"X-Opencode-Session": str(uuid.uuid4())},
        )
    else:
        raise ValueError(
            "Model configuration is incomplete. Please check your settings."
        )
