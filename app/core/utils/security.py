from argon2 import PasswordHasher

pwd_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return pwd_hasher.hash(password)


def verify_password(hashed_password: str, plain_password: str) -> bool:
    return pwd_hasher.verify(hashed_password, plain_password)
