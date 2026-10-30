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
