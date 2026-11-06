"""adicionar tabelas de 2fa

Revision ID: 1e9f2514bd63
Revises: 0b6b8dfb2daf
Create Date: 2026-11-06 10:21:31.479373

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1e9f2514bd63'
down_revision: Union[str, Sequence[str], None] = '0b6b8dfb2daf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "segredos_totp",
        sa.Column("utilizador_id", sa.Integer(), nullable=False),
        sa.Column("segredo_cifrado", sa.LargeBinary(), nullable=False),
        sa.Column("nonce", sa.LargeBinary(), nullable=False),
        sa.Column(
            "confirmado",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["utilizador_id"],
            ["utilizadores.id"],
        ),
        sa.PrimaryKeyConstraint("utilizador_id"),
    )
    op.create_table(
        "codigos_recuperacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("utilizador_id", sa.Integer(), nullable=False),
        sa.Column("hash", sa.Text(), nullable=False),
        sa.Column("usado_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["utilizador_id"],
            ["utilizadores.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("codigos_recuperacao")
    op.drop_table("segredos_totp")
