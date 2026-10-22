from app.core.security import (
    gerar_hash_palavra_passe,
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
