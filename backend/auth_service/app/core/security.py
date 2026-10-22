from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError


_password_hasher = PasswordHasher()


def gerar_hash_palavra_passe(palavra_passe: str) -> str:
    return _password_hasher.hash(palavra_passe)


def verificar_palavra_passe(palavra_passe: str, hash_guardado: str) -> bool:
    try:
        _password_hasher.verify(hash_guardado, palavra_passe)
    except (VerificationError, InvalidHashError):
        return False

    return True
