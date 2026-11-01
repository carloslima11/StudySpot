import pyotp


def verificar_codigo(secret, codigo):
    """Valida o código de 6 dígitos do 2FA (TOTP)."""
    return pyotp.TOTP(secret).verify(codigo, valid_window=1)