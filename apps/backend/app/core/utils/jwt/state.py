from app.core import settings
from app.core.utils.jwt.backends import TokenBackend

token_backend = TokenBackend(
    algorithm=settings.JWT_ALGORITHM,
    signing_key=settings.SECRET_KEY,
    leeway=settings.JWT_LEEWAY,
)
