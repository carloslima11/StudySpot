from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Callable

from app.core.config import Settings
from app.csp import ConfigCSP
from app.servico_reservas import ResumoLibertacao, libertar_e_realocar

log = logging.getLogger("studyspot.tarefas")


def executar_ciclo(fabrica_sessao, locks, agora: Callable, settings: Settings,
                   broker_saudavel: bool) -> ResumoLibertacao:
    from app.repo_sql import RepositorioSQL
    cfg = ConfigCSP(slot_minutos=settings.slot_minutos,
                    limite_diario_horas=settings.limite_diario_horas)
    with fabrica_sessao() as sessao:
        return libertar_e_realocar(
            RepositorioSQL(sessao), locks, agora=agora(),
            tolerancia=timedelta(minutes=settings.tolerancia_checkin_minutos),
            broker_saudavel=broker_saudavel, cfg=cfg)


async def ciclo_periodico(fabrica_sessao, locks, agora: Callable, settings: Settings,
                          broker_saudavel: Callable[[], bool]) -> None:
    while True:
        try:
            resumo = await asyncio.to_thread(
                executar_ciclo, fabrica_sessao, locks, agora, settings, broker_saudavel())
            if resumo.libertadas or resumo.realocadas or resumo.expiradas:
                log.info("libertadas=%s realocadas=%s expiradas=%s", resumo.libertadas,
                         [e for e, _ in resumo.realocadas], resumo.expiradas)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("falha no ciclo de libertação; nova tentativa no próximo ciclo")
        await asyncio.sleep(settings.tarefa_periodica_segundos)
