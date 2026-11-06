from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import requests


class ServicoIndisponivel(Exception):
    pass


class ErroAPI(Exception):
    pass


@dataclass
class Resposta:
    estado_http: int
    dados: Any

    @property
    def ok(self) -> bool:
        return 200 <= self.estado_http < 300

    @property
    def detalhe(self) -> str:
        if isinstance(self.dados, dict):
            d = self.dados.get("detail")
            if isinstance(d, str):
                return d
            if isinstance(d, list):
                msgs = [str(e.get("msg", "")).removeprefix("Value error, ")
                        for e in d if isinstance(e, dict)]
                if msgs:
                    return " ".join(msgs)
        return "O pedido não foi aceite pelo serviço de reservas."


class BookingAPI:
    def __init__(self, base_url: str, token_sessao: Optional[str] = None, timeout: float = 12.0) -> None:
        self.base = base_url.rstrip("/")
        self.cabecalhos = (
            {} if token_sessao is None else {"Authorization": f"Bearer {token_sessao}"}
        )
        self.timeout = timeout

    def _pedido(self, metodo: str, caminho: str, **kwargs) -> Resposta:
        cabecalhos = {**self.cabecalhos, **kwargs.pop("headers", {})}
        try:
            r = requests.request(metodo, self.base + caminho, headers=cabecalhos,
                                 timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise ServicoIndisponivel(
                "O serviço de reservas não está disponível.") from exc
        if r.status_code in (502, 504):
            raise ServicoIndisponivel(
                "O serviço de reservas não está disponível.")
        try:
            dados = r.json()
        except ValueError:
            dados = None
        return Resposta(r.status_code, dados)

    def _lista(self, caminho: str, **kwargs) -> list[dict]:
        r = self._pedido("GET", caminho, **kwargs)
        if not r.ok:
            raise ErroAPI(r.detalhe)
        return r.dados or []

    def salas(self) -> list[dict]:
        return self._lista("/api/salas")

    def ocupacao(self, dia: date) -> list[dict]:
        return self._lista("/api/salas/ocupacao", params={"dia": dia.isoformat()})

    def minhas(self) -> list[dict]:
        return self._lista("/api/reservas/minhas")

    def esperas(self) -> list[dict]:
        return self._lista("/api/reservas/espera")

    def sair_espera(self, espera_id: int) -> Resposta:
        return self._pedido("DELETE", f"/api/reservas/espera/{espera_id}")

    def criar(self, pedido: dict, chave: str) -> Resposta:
        return self._pedido("POST", "/api/reservas", json=pedido, headers={"Idempotency-Key": chave})

    def cancelar(self, reserva_id: int) -> Resposta:
        return self._pedido("DELETE", f"/api/reservas/{reserva_id}")

    def qr(self, reserva_id: int) -> Resposta:
        return self._pedido("GET", f"/api/reservas/{reserva_id}/qr")

    def vivo(self, caminho: str) -> bool:
        try:
            return self._pedido("GET", caminho).ok
        except ServicoIndisponivel:
            return False
