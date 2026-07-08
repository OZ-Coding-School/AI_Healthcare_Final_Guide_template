from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.utils.jwt.provider import JWTProvider
from app.models.user_models import User
from app.repositories.user_repository import UserRepository

security = HTTPBearer()


async def get_request_user(credential: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> User:
    token = credential.credentials
    verified = JWTProvider().verify_jwt(token=token, token_type="access")
    user_id = verified.payload["user_id"]
    user = await UserRepository().get_user_by_id(user_id)
    if not user:
        raise HTTPException(detail="Authenticate Failed.", status_code=status.HTTP_401_UNAUTHORIZED)
    return user
