"""
csp.py - Componente de Inteligência Artificial do projeto.
Coloquei de maniera a que ficasse pronto para a integração vom a base de dados.

Isto modela a atribuição de reservas como um Problema de Satisfação de Restrições
(CSP) <V, D, C>:

    V (variáveis)  : pedidos de reserva (novos ou em lista de espera)
    D (domínios)   : as salas de estudo (cada pedido recebe uma sala ou fica sem poratnto fica em espera)
    C (restrições) : estrutura, capacidade, janela de funcionamento,
                     sobreposição e limite diário por estudante
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, time, timedelta
from itertools import chain
from typing import Iterable, Optional

# Configuração e modelos de dados

@dataclass(frozen=True)
class ConfigCSP:
    slot_minutos: int = 30
    limite_diario_horas: float = 4.0
    estrategia: str = "fifo"


@dataclass(frozen=True)
class Sala:
    id: str
    capacidade: int
    abertura: time
    fecho: time
    ativa: bool = True

@dataclass(frozen=True)
class PedidoReserva:

    id: str
    estudante_id: str
    participantes: int
    inicio: datetime
    fim: datetime
    criado_em: datetime
    sala_id: Optional[str] = None

    @property
    def horas(self) -> float:
        return (self.fim - self.inicio).total_seconds() / 3600


@dataclass(frozen=True)
class Reserva:

    id: str
    sala_id: str
    estudante_id: str
    inicio: datetime
    fim: datetime

    @property
    def horas(self) -> float:
        return (self.fim - self.inicio).total_seconds() / 3600


@dataclass(frozen=True)
class PedidoEspera:

    id: str
    estudante_id: str
    participantes: int
    janela_inicio: datetime
    janela_fim: datetime
    duracao_minutos: int
    criado_em: datetime
    sala_id: Optional[str] = None

    @property
    def horas(self) -> float:
        return self.duracao_minutos / 60

    def inicios_possiveis(self, cfg: ConfigCSP) -> list[datetime]:
        if self.duracao_minutos <= 0 or cfg.slot_minutos <= 0:
            return []
        duracao = timedelta(minutes=self.duracao_minutos)
        passo = timedelta(minutes=cfg.slot_minutos)
        inicios: list[datetime] = []
        atual = self.janela_inicio
        while atual + duracao <= self.janela_fim:
            inicios.append(atual)
            atual += passo
        return inicios

    def concretizar(self, inicio: datetime) -> PedidoReserva:
        return PedidoReserva(
            id=self.id, estudante_id=self.estudante_id, participantes=self.participantes,
            inicio=inicio, fim=inicio + timedelta(minutes=self.duracao_minutos),
            criado_em=self.criado_em, sala_id=self.sala_id)


def para_espera(p: PedidoReserva) -> PedidoEspera:

    return PedidoEspera(
        id=p.id, estudante_id=p.estudante_id, participantes=p.participantes,
        janela_inicio=p.inicio, janela_fim=p.fim,
        duracao_minutos=int((p.fim - p.inicio).total_seconds() // 60),
        criado_em=p.criado_em, sala_id=p.sala_id)


Pedido = PedidoReserva | PedidoEspera   # o que o solver aceita como variável
Opcao = tuple[Sala, PedidoReserva]      # um valor do domínio: sala + horário concreto


@dataclass
class Resultado:
    valido: bool
    motivos: list[str] = field(default_factory=list)


@dataclass
class Resolucao:
    atribuicoes: dict[str, str] = field(default_factory=dict)
    horarios: dict[str, tuple[datetime, datetime]] = field(default_factory=dict)
    rejeitados: dict[str, list[str]] = field(default_factory=dict)
    lista_espera: list[str] = field(default_factory=list)

@dataclass
class Alternativas:
    """Sugestões quando um pedido é recusado (diagrama: 'Recusa com motivo e alternativas')."""
    salas: list[str] = field(default_factory=list)  # outras salas livres no MESMO horário
    # (sala_id, inicio, fim): horários próximos com a mesma duração
    horarios: list[tuple[str, datetime, datetime]] = field(default_factory=list)


Atribuicao = Resolucao


def _minutos_do_dia(t: datetime) -> int:
    return t.hour * 60 + t.minute


def verificar_estrutura(p: PedidoReserva, cfg: ConfigCSP) -> Optional[str]:

    if p.participantes < 1:
        return "O número de participantes tem de ser pelo menos 1."
    if p.fim <= p.inicio:
        return "A hora de fim tem de ser posterior à hora de início."
    if p.inicio.date() != p.fim.date():
        return "A reserva tem de começar e terminar no mesmo dia."
    for t in (p.inicio, p.fim):
        if t.second or t.microsecond or _minutos_do_dia(t) % cfg.slot_minutos:
            return f"Os horários têm de estar alinhados a blocos de {cfg.slot_minutos} minutos."
    return None


def verificar_ativa(sala: Sala) -> Optional[str]:

    if not sala.ativa:
        return f"A sala {sala.id} não está disponível para reservas."
    return None


def verificar_capacidade(p: PedidoReserva, sala: Sala) -> Optional[str]:

    if p.participantes > sala.capacidade:
        return (f"A sala {sala.id} comporta {sala.capacidade} pessoas "
                f"e o pedido tem {p.participantes}.")
    return None


def verificar_janela(p: PedidoReserva, sala: Sala) -> Optional[str]:

    if p.inicio.time() < sala.abertura or p.fim.time() > sala.fecho:
        return (f"A sala {sala.id} funciona entre {sala.abertura:%H:%M} "
                f"e {sala.fecho:%H:%M}.")
    return None


def verificar_sobreposicao(p: PedidoReserva, sala: Sala,
                           reservas: Iterable[Reserva]) -> Optional[str]:

    for r in reservas:
        if r.sala_id == sala.id and p.inicio < r.fim and r.inicio < p.fim:
            return f"A sala {sala.id} já está reservada entre {r.inicio:%H:%M} e {r.fim:%H:%M}."
    return None


def verificar_limite_diario(p: PedidoReserva, reservas: Iterable[Reserva],
                            cfg: ConfigCSP) -> Optional[str]:

    dia = p.inicio.date()
    ja_reservadas = sum(
        r.horas for r in reservas
        if r.estudante_id == p.estudante_id and r.inicio.date() == dia
    )
    if ja_reservadas + p.horas > cfg.limite_diario_horas:
        return (f"Limite diário de {cfg.limite_diario_horas:g}h excedido "
                f"({ja_reservadas:g}h já reservadas + {p.horas:g}h pedidas).")
    return None


def validar_pedido(p: PedidoReserva, sala: Sala, reservas: Iterable[Reserva],
                   cfg: ConfigCSP = ConfigCSP()) -> Resultado:

    reservas = list(reservas)
    verificacoes = (
        verificar_estrutura(p, cfg),
        verificar_ativa(sala),
        verificar_capacidade(p, sala),
        verificar_janela(p, sala),
        verificar_sobreposicao(p, sala, reservas),
        verificar_limite_diario(p, reservas, cfg),
    )
    motivos = [m for m in verificacoes if m is not None]
    return Resultado(valido=not motivos, motivos=motivos)

# Solver

def _dominio(p: Pedido, salas: list[Sala], cfg: ConfigCSP) -> list[Opcao]:

    if isinstance(p, PedidoEspera):
        concretos = [p.concretizar(i) for i in p.inicios_possiveis(cfg)]
    else:
        concretos = [p]
    opcoes: list[Opcao] = []
    for c in concretos:
        if verificar_estrutura(c, cfg):
            continue
        for s in salas:
            if ((c.sala_id is None or s.id == c.sala_id)
                    and verificar_ativa(s) is None
                    and verificar_capacidade(c, s) is None
                    and verificar_janela(c, s) is None):
                opcoes.append((s, c))
    opcoes.sort(key=lambda o: (o[1].inicio, o[0].capacidade, o[0].id))
    return opcoes


def _compativel(p: PedidoReserva, sala: Sala, reservas: Iterable[Reserva],
                cfg: ConfigCSP) -> bool:

    reservas = list(reservas)
    return (verificar_sobreposicao(p, sala, reservas) is None
            and verificar_limite_diario(p, reservas, cfg) is None)


def _tentativa(p: PedidoReserva, sala: Sala) -> Reserva:
    return Reserva(id=f"tmp-{p.id}", sala_id=sala.id, estudante_id=p.estudante_id,
                   inicio=p.inicio, fim=p.fim)


def _motivos_rejeicao(p: Pedido, salas: list[Sala], reservas: list[Reserva],
                      cfg: ConfigCSP, opcoes: list[Opcao]) -> list[str]:
    """Explica porque um pedido ficou sem sala: motivos da sala com menos violações."""
    candidatas = [s for s in salas if p.sala_id is None or s.id == p.sala_id]
    if not candidatas:
        return ["Não existe nenhuma sala elegível para este pedido."]
    if isinstance(p, PedidoEspera):
        if not p.inicios_possiveis(cfg):
            return ["A duração pedida não cabe na janela indicada (ou é inválida)."]
        if opcoes:  # válido em si: falta vaga ou há excesso de horas no dia
            limites = [verificar_limite_diario(c, reservas, cfg) for _, c in opcoes]
            if all(limites):
                return [limites[0]]
            return [f"Não há horário livre entre {p.janela_inicio:%H:%M} e {p.janela_fim:%H:%M}."]
        base = p.concretizar(p.janela_inicio)
    else:
        base = p
    melhor = min((validar_pedido(base, s, reservas, cfg).motivos for s in candidatas), key=len)
    return melhor or ["Não foi possível alocar sala (conflito com outros pedidos)."]


def resolver(pedidos: Iterable[Pedido], salas: Iterable[Sala],
             reservas_fixas: Iterable[Reserva] = (),
             cfg: ConfigCSP = ConfigCSP()) -> Resolucao:

    salas = list(salas)
    existentes = list(reservas_fixas)
    ordem = sorted(pedidos, key=lambda p: (p.criado_em, p.id))
    dominios = {p.id: _dominio(p, salas, cfg) for p in ordem}

    if cfg.estrategia == "fifo":
        atribuicoes = _resolver_fifo(ordem, dominios, existentes, cfg)
    elif cfg.estrategia == "maximizar":
        atribuicoes = _resolver_maximizar(ordem, dominios, existentes, cfg)
    else:
        raise ValueError(f"Estratégia desconhecida: {cfg.estrategia!r}")

    resolucao = Resolucao(
        atribuicoes={pid: s.id for pid, (s, _) in atribuicoes.items()},
        horarios={pid: (c.inicio, c.fim) for pid, (_, c) in atribuicoes.items()},
    )
    finais = existentes + [_tentativa(c, s) for s, c in atribuicoes.values()]
    for p in ordem:
        if p.id not in atribuicoes:
            # Validar contra as reservas finais SEM contar uma tentativa do próprio pedido
            resolucao.rejeitados[p.id] = _motivos_rejeicao(p, salas, finais, cfg, dominios[p.id])
            # Só espera quem é válido em si (domínio não vazio) e não esbarra no
            # limite diário em todas as opções: o que falta é ficar uma vaga livre.
            if any(verificar_limite_diario(c, finais, cfg) is None for _, c in dominios[p.id]):
                resolucao.lista_espera.append(p.id)
    return resolucao


def _resolver_fifo(ordem, dominios, existentes, cfg) -> dict:
    atribuicoes: dict = {}
    tentativas: list[Reserva] = []
    for p in ordem:
        for sala, c in dominios[p.id]:
            if _compativel(c, sala, chain(existentes, tentativas), cfg):
                atribuicoes[p.id] = (sala, c)
                tentativas.append(_tentativa(c, sala))
                break
    return atribuicoes


def _resolver_maximizar(ordem, dominios, existentes, cfg) -> dict:
    melhor: dict = {}
    atual: dict = {}
    tentativas: list[Reserva] = []

    def bt(i: int) -> None:
        nonlocal melhor
        # Poda: mesmo atribuindo todos os restantes, não superaria o melhor atual.
        if len(atual) + (len(ordem) - i) <= len(melhor):
            return
        if i == len(ordem):
            melhor = dict(atual)
            return
        p = ordem[i]
        for sala, c in dominios[p.id]:                    # 1.º tenta atribuir
            if _compativel(c, sala, chain(existentes, tentativas), cfg):
                atual[p.id] = (sala, c)
                tentativas.append(_tentativa(c, sala))
                bt(i + 1)
                tentativas.pop()
                del atual[p.id]
        bt(i + 1)                                         # 2.º deixa sem sala

    bt(0)
    return melhor


def slots_ocupados(inicio: datetime, fim: datetime,
                   cfg: ConfigCSP = ConfigCSP()) -> list[datetime]:

    passo = timedelta(minutes=cfg.slot_minutos)
    slots: list[datetime] = []
    atual = inicio
    while atual < fim:
        slots.append(atual)
        atual += passo
    return slots


def sugerir_alternativas(pedido: PedidoReserva, salas: Iterable[Sala],
                         reservas_fixas: Iterable[Reserva] = (),
                         cfg: ConfigCSP = ConfigCSP(),
                         max_horarios: int = 3) -> Alternativas:

    salas = list(salas)
    fixas = list(reservas_fixas)
    resultado = Alternativas()
    if verificar_estrutura(pedido, cfg):
        return resultado  # sem duração/horário válidos não há o que comparar

    for s in sorted(salas, key=lambda s: (s.capacidade, s.id)):
        if s.id != pedido.sala_id and validar_pedido(pedido, s, fixas, cfg).valido:
            resultado.salas.append(s.id)

    duracao = pedido.fim - pedido.inicio
    passo = timedelta(minutes=cfg.slot_minutos)
    candidatos: list[tuple[timedelta, int, str, datetime, datetime]] = []
    for s in salas:
        if verificar_ativa(s) or verificar_capacidade(pedido, s):
            continue
        ini = datetime.combine(pedido.inicio.date(), s.abertura)
        limite = datetime.combine(pedido.inicio.date(), s.fecho)
        while ini + duracao <= limite:
            if ini != pedido.inicio:  # o horário pedido já está coberto por `salas`
                alt = replace(pedido, inicio=ini, fim=ini + duracao)
                if validar_pedido(alt, s, fixas, cfg).valido:
                    candidatos.append((abs(ini - pedido.inicio), s.capacidade,
                                       s.id, ini, ini + duracao))
            ini += passo
    candidatos.sort(key=lambda c: c[:4])
    resultado.horarios = [(c[2], c[3], c[4]) for c in candidatos[:max_horarios]]
    return resultado


class MotorCSP:
    """Fachada que espelha a classe MotorCSP do diagrama de classes.

    Guarda a configuração e expõe as operações do módulo, para os serviços
    FastAPI poderem fazer `MotorCSP(cfg).resolver(pedidos, salas, reservas_fixas)`.
    """

    def __init__(self, cfg: ConfigCSP = ConfigCSP()) -> None:
        self.cfg = cfg

    def resolver(self, pedidos: Iterable[Pedido], salas: Iterable[Sala],
                 reservas_fixas: Iterable[Reserva] = ()) -> Atribuicao:
        return resolver(pedidos, salas, reservas_fixas, self.cfg)

    def validar(self, pedido: PedidoReserva, sala: Sala,
                reservas_fixas: Iterable[Reserva] = ()) -> Resultado:
        return validar_pedido(pedido, sala, reservas_fixas, self.cfg)

    def sugerir_alternativas(self, pedido: PedidoReserva, salas: Iterable[Sala],
                             reservas_fixas: Iterable[Reserva] = ()) -> Alternativas:
        return sugerir_alternativas(pedido, salas, reservas_fixas, self.cfg)


_EPSILON = 1e-9  # tolerância para somas de horas em vírgula flutuante


def validar_capacidade(num_pessoas: int, capacidade_sala: int) -> bool:
    """Restrição de lotação: True se a sala comporta o grupo.

    Um grupo com exatamente a capacidade da sala é aceite.
    """
    return num_pessoas <= capacidade_sala


def validar_horario(inicio: time, fim: time,
                    horario_abertura: time, horario_fecho: time) -> bool:
    """Restrição de horário: True se inicio < fim e o intervalo cabe no horário operacional.

    "Contido" inclui os extremos: começar à hora de abertura ou acabar à hora de
    fecho é válido. Trabalha com horas do mesmo dia.
    """
    return inicio < fim and horario_abertura <= inicio and fim <= horario_fecho


def validar_limite_estudante(estudante_id: str, horas_solicitadas: float,
                             historico_dia: dict[str, float],
                             limite_diario: float = 4.0) -> bool:
    """Restrição do estudante: True se (horas já reservadas hoje + pedidas) <= limite.

    `historico_dia` mapeia estudante_id -> horas já reservadas nesse dia.
    """
    ja_reservadas = historico_dia.get(estudante_id, 0.0)
    return ja_reservadas + horas_solicitadas <= limite_diario + _EPSILON


def validar_reserva_csp(reserva: dict, salas_info: dict[str, int],
                        horario_abertura: time, horario_fecho: time,
                        historico_dia: dict[str, float],
                        limite_diario: float = 4.0) -> tuple[bool, str]:
    """Valida um pedido contra todas as restrições, por ordem, e explica o resultado.

    `reserva` é um dicionário com as chaves: estudante_id, sala_id, num_pessoas,
    inicio e fim (estes dois, `datetime`). `salas_info` mapeia sala_id -> capacidade.
    Devolve (True, "Reserva válida ...") ou (False, motivo da PRIMEIRA violação).
    """
    campos = ("estudante_id", "sala_id", "num_pessoas", "inicio", "fim")
    em_falta = [c for c in campos if c not in reserva]
    if em_falta:
        return False, f"Pedido incompleto: faltam os campos {', '.join(em_falta)}."

    estudante_id = reserva["estudante_id"]
    sala_id = reserva["sala_id"]
    num_pessoas = reserva["num_pessoas"]
    inicio: datetime = reserva["inicio"]
    fim: datetime = reserva["fim"]

    if sala_id not in salas_info:
        return False, f"A sala {sala_id} não existe."
    if num_pessoas < 1:
        return False, "O número de pessoas tem de ser pelo menos 1."
    if fim <= inicio:
        return False, "A hora de fim tem de ser posterior à hora de início."
    if inicio.date() != fim.date():
        return False, "A reserva tem de começar e terminar no mesmo dia."

    horas = (fim - inicio).total_seconds() / 3600  # duração em horas (float)

    capacidade = salas_info[sala_id]
    if not validar_capacidade(num_pessoas, capacidade):
        return False, (f"A sala {sala_id} comporta {capacidade} pessoas "
                       f"e o pedido tem {num_pessoas}.")
    if not validar_horario(inicio.time(), fim.time(), horario_abertura, horario_fecho):
        return False, (f"O horário {inicio:%H:%M}-{fim:%H:%M} está fora do funcionamento "
                       f"({horario_abertura:%H:%M}-{horario_fecho:%H:%M}).")
    if not validar_limite_estudante(estudante_id, horas, historico_dia, limite_diario):
        ja = historico_dia.get(estudante_id, 0.0)
        return False, (f"O estudante {estudante_id} excederia o limite diário de "
                       f"{limite_diario:g}h ({ja:g}h já reservadas + {horas:g}h pedidas).")
    return True, (f"Reserva válida: sala {sala_id}, {num_pessoas} pessoas, "
                  f"{inicio:%H:%M}-{fim:%H:%M} ({horas:g}h).")


def sugerir_sala_alternativa(reserva: dict, salas_info: dict[str, int],
                             horario_abertura: time, horario_fecho: time,
                             historico_dia: dict[str, float],
                             limite_diario: float = 4.0,
                             reservas_existentes: Iterable[dict] = ()) -> Optional[str]:

    sala_pedida = reserva.get("sala_id")
    if sala_pedida not in salas_info:
        return None
    if validar_capacidade(reserva["num_pessoas"], salas_info[sala_pedida]):
        return None  # a lotação não é o problema: trocar de sala não ajuda

    existentes = list(reservas_existentes)
    candidatas: list[tuple[int, str]] = []
    for sala_id, capacidade in salas_info.items():
        if sala_id == sala_pedida or not validar_capacidade(reserva["num_pessoas"], capacidade):
            continue
        valido, _ = validar_reserva_csp({**reserva, "sala_id": sala_id}, salas_info,
                                        horario_abertura, horario_fecho,
                                        historico_dia, limite_diario)
        ocupada = any(e["sala_id"] == sala_id and reserva["inicio"] < e["fim"]
                      and e["inicio"] < reserva["fim"] for e in existentes)
        if valido and not ocupada:
            candidatas.append((capacidade, sala_id))
    return min(candidatas)[1] if candidatas else None


# Demonstração monstra


def _demonstracao() -> None:
    abertura, fecho = time(8, 0), time(22, 0)
    salas = {"A1": 4, "B2": 8, "C3": 12}
    dia = (2026, 10, 20)

    def pedido(estudante: str, sala: str, pessoas: int, ini: tuple, fim: tuple) -> dict:
        return {"estudante_id": estudante, "sala_id": sala, "num_pessoas": pessoas,
                "inicio": datetime(*dia, *ini), "fim": datetime(*dia, *fim)}

    casos = [
        ("Caso 1 (sucesso): 3 pessoas na sala A1 (cap. 4), 10:00-11:30",
         pedido("ana", "A1", 3, (10, 0), (11, 30)), {}),
        ("Caso 2 (lotação): 6 pessoas na sala A1 (cap. 4)",
         pedido("bruno", "A1", 6, (10, 0), (11, 0)), {}),
        ("Caso 3a (horário): 07:00-08:30, a sala só abre às 08:00",
         pedido("carla", "B2", 2, (7, 0), (8, 30)), {}),
        ("Caso 3b (horário): fim (09:00) anterior ao início (10:00)",
         pedido("carla", "B2", 2, (10, 0), (9, 0)), {}),
        ("Caso 4 (limite): estudante com 3h já reservadas pede mais 1,5h",
         pedido("diogo", "B2", 2, (14, 0), (15, 30)), {"diogo": 3.0}),
    ]
    for titulo, reserva, historico in casos:
        valida, mensagem = validar_reserva_csp(reserva, salas, abertura, fecho, historico)
        print(f"{titulo}\n  -> {'ACEITE' if valida else 'REJEITADA'}: {mensagem}")
        if not valida:
            alternativa = sugerir_sala_alternativa(reserva, salas, abertura, fecho, historico)
            if alternativa:
                print(f"  -> Sugestão: sala {alternativa} ({salas[alternativa]} lugares)")
        print()


if __name__ == "__main__":
    _demonstracao()


"""" Rapazes isto aqui só vai correr mesmo bem quando tivermos a base de dados operacional"""