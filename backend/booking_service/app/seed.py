from datetime import time

from sqlalchemy import select

from app.models import Dispositivo, Sala
from app.repo_sql import criar_tabelas, get_sessionmaker

SALAS_EXEMPLO = [
    ("Sala 1", 4), ("Sala 2", 6), ("Sala 3", 8), ("Sala 4", 12),
]


def semear() -> int:
    criar_tabelas()
    with get_sessionmaker()() as sessao:
        if sessao.scalars(select(Sala.id).limit(1)).first() is not None:
            return 0
        salas = [Sala(nome=n, capacidade=c, abertura=time(8, 0), fecho=time(22, 0), ativa=True)
                 for n, c in SALAS_EXEMPLO]
        sessao.add_all(salas)
        sessao.flush()
        sessao.add_all(Dispositivo(sala_id=s.id, ativo=True) for s in salas)
        sessao.commit()
        return len(salas)


if __name__ == "__main__":
    print(f"{semear()} salas criadas")
