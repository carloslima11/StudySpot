import pytest
from cryptography.exceptions import InvalidTag

from app.core.security import (
    cifrar_segredo_totp,
    decifrar_segredo_totp,
)

from datetime import datetime, timezone

import pyotp

from app.core.security import (
    cifrar_segredo_totp,
    decifrar_segredo_totp,
    gerar_hash_palavra_passe,
    gerar_segredo_totp,
    verificar_codigo_totp,
    verificar_palavra_passe,
)


def test_hash_e_verificacao_de_palavra_passe() -> None:
    palavra_passe = "Exemplo-seguro-123"
    hash_guardado = gerar_hash_palavra_passe(palavra_passe)

    assert hash_guardado != palavra_passe
    assert verificar_palavra_passe(palavra_passe, hash_guardado)


def test_rejeita_palavra_passe_incorreta() -> None:
    hash_guardado = gerar_hash_palavra_passe("Exemplo-seguro-123")

    assert not verificar_palavra_passe("Outra-palavra-456", hash_guardado)


def test_rejeita_hash_invalido() -> None:
    assert not verificar_palavra_passe(
        "Exemplo-seguro-123", "isto-nao-e-um-hash")


def test_cifra_e_decifra_segredo_totp() -> None:
    segredo = "SEGREDO_DE_TESTE"
    chave_hex = "11" * 32

    cifrado, nonce = cifrar_segredo_totp(segredo, chave_hex)

    assert cifrado != segredo.encode("utf-8")
    assert len(nonce) == 12
    assert decifrar_segredo_totp(cifrado, nonce, chave_hex) == segredo


def test_rejeita_chave_incorreta_ao_decifrar_totp() -> None:
    cifrado, nonce = cifrar_segredo_totp("SEGREDO_DE_TESTE", "11" * 32)

    with pytest.raises(InvalidTag):
        decifrar_segredo_totp(cifrado, nonce, "22" * 32)


def test_gera_segredo_totp_base32_de_160_bits() -> None:
    segredo = gerar_segredo_totp()

    assert len(segredo) == 32
    assert all(
        caractere in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for caractere in segredo)


@pytest.mark.parametrize("desvio", [0, -1, 1])
def test_verifica_codigo_totp_no_passo_atual_e_adjacentes(
    desvio: int,
) -> None:
    segredo = "JBSWY3DPEHPK3PXP"
    instante = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
    totp = pyotp.TOTP(segredo, digits=6, interval=30)
    passo_esperado = totp.timecode(instante) + desvio
    codigo = totp.generate_otp(passo_esperado)

    assert verificar_codigo_totp(segredo, codigo, instante) == passo_esperado


@pytest.mark.parametrize("codigo", ["12345", "1234567", "abcdef", "12a456"])
def test_rejeita_codigo_totp_com_formato_invalido(codigo: str) -> None:
    instante = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)

    assert verificar_codigo_totp("JBSWY3DPEHPK3PXP", codigo, instante) is None
