from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timedelta

_VERSAO = "SS1"


class TokenInvalido(ValueError):
    pass


@dataclass(frozen=True)
class TokenCheckin:
    texto: str
    expira_em: datetime


def _assinar(segredo: bytes, reserva_id: int, sala_id: int, expira: int) -> str:
    mensagem = f"{_VERSAO}.{reserva_id}.{sala_id}.{expira}".encode()
    return hmac.new(segredo, mensagem, hashlib.sha256).hexdigest()[:32]


def gerar_token(segredo: bytes, reserva_id: int, sala_id: int, agora: datetime,
                validade: timedelta = timedelta(minutes=2)) -> TokenCheckin:
    expira_em = (agora + validade).replace(microsecond=0)
    expira = int(expira_em.strftime("%Y%m%d%H%M%S"))
    assinatura = _assinar(segredo, reserva_id, sala_id, expira)
    return TokenCheckin(f"{_VERSAO}.{reserva_id}.{expira}.{assinatura}", expira_em)


def validar_token(segredo: bytes, texto: str, sala_id: int, agora: datetime) -> int:
    partes = texto.strip().split(".")
    if len(partes) != 4 or partes[0] != _VERSAO:
        raise TokenInvalido("formato desconhecido")
    try:
        reserva_id, expira = int(partes[1]), int(partes[2])
        expira_em = datetime.strptime(partes[2], "%Y%m%d%H%M%S")
    except ValueError as exc:
        raise TokenInvalido("formato desconhecido") from exc
    if not hmac.compare_digest(partes[3], _assinar(segredo, reserva_id, sala_id, expira)):
        raise TokenInvalido("assinatura inválida ou sala errada")
    if agora > expira_em:
        raise TokenInvalido("QR code expirado")
    return reserva_id
