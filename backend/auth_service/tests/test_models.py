from sqlalchemy import create_engine, inspect
from app.models import Base


def test_esquema_de_utilizadores_cria_tabela_em_sqlite_em_memoria() -> None:
    engine = create_engine("sqlite://")

    Base.metadata.create_all(engine)

    inspector = inspect(engine)
    assert "utilizadores" in inspector.get_table_names()

    colunas = {coluna["name"]
               for coluna in inspector.get_columns("utilizadores")}
    assert {
        "id",
        "nome",
        "email",
        "palavra_passe_hash",
        "perfil",
        "ultimo_passo_totp",
        "ativo",
        "criado_em",
    } <= colunas

    unicas = inspector.get_unique_constraints("utilizadores")
    assert any("email" in constraint["column_names"] for constraint in unicas)

    tabelas = set(inspector.get_table_names())
    assert {"segredos_totp", "codigos_recuperacao"} <= tabelas

    colunas_totp = {
        coluna["name"]
        for coluna in inspector.get_columns("segredos_totp")
    }
    assert {
        "utilizador_id",
        "segredo_cifrado",
        "nonce",
        "confirmado",
        "criado_em",
    } <= colunas_totp

    fks_totp = inspector.get_foreign_keys("segredos_totp")
    assert any(
        fk["referred_table"] == "utilizadores"
        and fk["constrained_columns"] == ["utilizador_id"]
        for fk in fks_totp
    )

    colunas_recuperacao = {
        coluna["name"]
        for coluna in inspector.get_columns("codigos_recuperacao")
    }
    assert {
        "id",
        "utilizador_id",
        "hash",
        "usado_em",
    } <= colunas_recuperacao

    fks_recuperacao = inspector.get_foreign_keys("codigos_recuperacao")
    assert any(
        fk["referred_table"] == "utilizadores"
        and fk["constrained_columns"] == ["utilizador_id"]
        for fk in fks_recuperacao
    )
