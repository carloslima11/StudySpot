from datetime import datetime
from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Utilizador(Base):
    __tablename__ = "utilizadores"
    __table_args__ = (
        CheckConstraint(
            "perfil IN ('estudante', 'administrador')",
            name="ck_utilizadores_perfil",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(
        String(254), unique=True, nullable=False)
    palavra_passe_hash: Mapped[str] = mapped_column(Text, nullable=False)
    perfil: Mapped[str] = mapped_column(String(20), nullable=False)
    ultimo_passo_totp: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
