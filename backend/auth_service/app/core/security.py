from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import datetime, timezone
import hmac
import re
import pyotp

_password_hasher = PasswordHasher()


def gerar_hash_palavra_passe(palavra_passe: str) -> str:
    return _password_hasher.hash(palavra_passe)


def verificar_palavra_passe(palavra_passe: str, hash_guardado: str) -> bool:
    try:
        _password_hasher.verify(hash_guardado, palavra_passe)
    except (VerificationError, InvalidHashError):
        return False

    return True


def cifrar_segredo_totp(segredo: str, chave_hex: str) -> tuple[bytes, bytes]:
    chave = bytes.fromhex(chave_hex)
    if len(chave) != 32:
        raise ValueError("A chave de cifragem TOTP deve ter 32 bytes.")

    nonce = os.urandom(12)
    cifrado = AESGCM(chave).encrypt(nonce, segredo.encode("utf-8"), None)
    return cifrado, nonce


def decifrar_segredo_totp(
    cifrado: bytes,
    nonce: bytes,
    chave_hex: str,
) -> str:
    chave = bytes.fromhex(chave_hex)
    if len(chave) != 32:
        raise ValueError("A chave de cifragem TOTP deve ter 32 bytes.")

    segredo = AESGCM(chave).decrypt(nonce, cifrado, None)
    return segredo.decode("utf-8")


def gerar_segredo_totp() -> str:
    return pyotp.random_base32(length=32)


def verificar_codigo_totp(
    segredo: str,
    codigo: str,
    agora: datetime | None = None,
) -> int | None:
    if re.fullmatch(r"[0-9]{6}", codigo) is None:
        return None

    instante = agora or datetime.now(timezone.utc)
    totp = pyotp.TOTP(segredo, digits=6, interval=30)
    passo_atual = totp.timecode(instante)

    for desvio in (0, -1, 1):
        passo = passo_atual + desvio
        codigo_esperado = totp.generate_otp(passo)
        if hmac.compare_digest(codigo_esperado, codigo):
            return passo

    return None
