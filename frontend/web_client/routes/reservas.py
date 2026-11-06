import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from markupsafe import Markup

from services.booking_api import BookingAPI, ErroAPI, ServicoIndisponivel

reservas_bp = Blueprint("reservas", __name__)

LISBOA = ZoneInfo("Europe/Lisbon")
INICIO_GRELHA = time(8, 0)
FIM_GRELHA = time(22, 0)
PASSO = timedelta(minutes=30)
LIMITE_HORAS = 4
DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SÁB", "DOM"]
MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]


def agora() -> datetime:
    return datetime.now(LISBOA).replace(tzinfo=None)


def api() -> BookingAPI:
    return BookingAPI(
        current_app.config["BOOKING_API_URL"],
        session["token_sessao"],
    )


def para_data(texto: str) -> datetime:
    return datetime.fromisoformat(texto)


def horas(inicio: datetime, fim: datetime) -> float:
    return (fim - inicio).total_seconds() / 3600


def formatar_horas(valor: float) -> str:
    return f"{valor:g}".replace(".", ",") + " h"


def qr_svg(texto: str):
    try:
        import segno
    except ImportError:
        return None
    return Markup(segno.make(texto, error="m").svg_inline(scale=6, border=2, dark="#111111", light="#ffffff"))


@reservas_bp.before_request
def exigir_sessao():
    if not session.get("token_sessao"):
        return redirect(url_for("auth.login"))


@reservas_bp.app_context_processor
def dados_comuns():
    return {"utilizador_email": session.get("utilizador_email", "")}


@reservas_bp.app_template_filter("hora")
def filtro_hora(valor) -> str:
    if isinstance(valor, str):
        valor = para_data(valor)
    return valor.strftime("%H:%M")


@reservas_bp.app_template_filter("dia_curto")
def filtro_dia_curto(valor) -> str:
    if isinstance(valor, str):
        valor = para_data(valor)
    return f"{DIAS[valor.weekday()]} · {valor.day:02d} {MESES[valor.month - 1]}"


def grelha(salas: list[dict], ocupacao: list[dict], dia: date, pedido=None) -> dict:
    slots = []
    t = datetime.combine(dia, INICIO_GRELHA)
    while t < datetime.combine(dia, FIM_GRELHA):
        slots.append(t)
        t += PASSO
    linhas = []
    for sala in salas:
        abre = datetime.combine(dia, time.fromisoformat(sala["abertura"]))
        fecha = datetime.combine(dia, time.fromisoformat(sala["fecho"]))
        ocupadas = [(para_data(o["inicio"]), para_data(o["fim"]), o["minha"])
                    for o in ocupacao if o["sala_id"] == sala["id"]]
        celulas = []
        for inicio in slots:
            fim = inicio + PASSO
            estado = "livre"
            if inicio < abre or fim > fecha:
                estado = "fechada"
            elif pedido and pedido["sala_id"] == sala["id"] and pedido["inicio"] <= inicio < pedido["fim"]:
                estado = "pedido"
            else:
                for oi, of, minha in ocupadas:
                    if oi < fim and inicio < of:
                        estado = "minha" if minha else "ocupada"
                        break
            celulas.append({"estado": estado, "titulo": f"{inicio:%H:%M}–{fim:%H:%M}"})
        linhas.append({"sala": sala, "celulas": celulas})
    return {"horas": [s.strftime("%H:%M") for s in slots[::2]], "linhas": linhas}


def regras_cumpridas(reserva: dict, sala: dict, minhas: list[dict]) -> list[dict]:
    inicio, fim = para_data(reserva["inicio"]), para_data(reserva["fim"])
    total = sum(horas(para_data(r["inicio"]), para_data(r["fim"])) for r in minhas
                if r["estado"] in ("confirmada", "concluida")
                and para_data(r["inicio"]).date() == inicio.date())
    total = max(total, horas(inicio, fim))
    return [
        {"nome": "Lotação", "ok": True,
         "detalhe": f"{reserva['n_pessoas']} pessoas cabem nos {sala['capacidade']} lugares da {sala['nome']}"},
        {"nome": "Horário da sala", "ok": True,
         "detalhe": f"{inicio:%H:%M}–{fim:%H:%M} está dentro de {sala['abertura'][:5]}–{sala['fecho'][:5]}"},
        {"nome": "Sem sobreposição", "ok": True,
         "detalhe": f"A {sala['nome']} fica tua das {inicio:%H:%M} às {fim:%H:%M}"},
        {"nome": "Limite diário", "ok": True,
         "detalhe": f"{formatar_horas(total)} de {LIMITE_HORAS} h reservadas nesse dia"},
    ]


def proxima_meia_hora() -> datetime:
    t = agora().replace(second=0, microsecond=0)
    return t + timedelta(minutes=(30 - t.minute % 30) % 30 or 30)


@reservas_bp.route("/reservar", methods=["GET", "POST"])
def nova():
    fonte = request.form if request.method == "POST" else request.args
    sugestao = proxima_meia_hora()
    valores = {
        "dia": fonte.get("dia") or sugestao.date().isoformat(),
        "pessoas": fonte.get("pessoas") or "2",
        "inicio": fonte.get("inicio") or sugestao.strftime("%H:%M"),
        "fim": fonte.get("fim") or (sugestao + timedelta(hours=1)).strftime("%H:%M"),
        "sala": fonte.get("sala") or "",
        "espera": bool(fonte.get("espera")),
        "janela_fim": fonte.get("janela_fim") or "",
    }
    try:
        dia = date.fromisoformat(valores["dia"])
    except ValueError:
        dia = sugestao.date()
        valores["dia"] = dia.isoformat()

    resultado = None
    pedido_grelha = None
    cliente = api()
    if request.method == "POST":
        pedido = {
            "n_pessoas": int(valores["pessoas"]) if valores["pessoas"].isdigit() else 0,
            "inicio": f"{valores['dia']}T{valores['inicio']}:00",
            "fim": f"{valores['dia']}T{valores['fim']}:00",
            "sala_id": int(valores["sala"]) if valores["sala"].isdigit() else None,
        }
        if valores["espera"] and valores["janela_fim"]:
            pedido["janela_fim"] = f"{valores['dia']}T{valores['janela_fim']}:00"
        try:
            r = cliente.criar(pedido, request.form.get("chave") or uuid.uuid4().hex)
            if isinstance(r.dados, dict) and "estado" in r.dados:
                resultado = r.dados
            else:
                resultado = {"estado": "erro", "motivos": [r.detalhe]}
        except ServicoIndisponivel as exc:
            resultado = {"estado": "erro", "motivos": [str(exc)]}

    salas, ocupacao, minhas = [], [], []
    try:
        salas = cliente.salas()
        ocupacao = cliente.ocupacao(dia)
        minhas = cliente.minhas()
    except (ServicoIndisponivel, ErroAPI) as exc:
        flash(str(exc), "erro")
    salas_por_id = {s["id"]: s for s in salas}

    regras = None
    if resultado and resultado.get("reserva"):
        reserva = resultado["reserva"]
        sala = salas_por_id.get(reserva["sala_id"])
        if sala:
            regras = regras_cumpridas(reserva, sala, minhas)
            pedido_grelha = None
    elif request.method == "GET" and valores["sala"].isdigit():
        try:
            pedido_grelha = {"sala_id": int(valores["sala"]),
                             "inicio": datetime.fromisoformat(f"{valores['dia']}T{valores['inicio']}"),
                             "fim": datetime.fromisoformat(f"{valores['dia']}T{valores['fim']}")}
        except ValueError:
            pedido_grelha = None

    alternativas = []
    if resultado and resultado.get("alternativas"):
        for sala_id in resultado["alternativas"].get("salas", []):
            sala = salas_por_id.get(sala_id, {"nome": f"Sala {sala_id}"})
            alternativas.append({"sala_id": sala_id, "sala": sala["nome"],
                                 "inicio": datetime.fromisoformat(f"{valores['dia']}T{valores['inicio']}"),
                                 "fim": datetime.fromisoformat(f"{valores['dia']}T{valores['fim']}")})
        for h in resultado["alternativas"].get("horarios", []):
            sala = salas_por_id.get(h["sala_id"], {"nome": f"Sala {h['sala_id']}"})
            alternativas.append({"sala_id": h["sala_id"], "sala": sala["nome"],
                                 "inicio": para_data(h["inicio"]), "fim": para_data(h["fim"])})
        vistas = set()
        alternativas = [a for a in alternativas
                        if (a["sala_id"], a["inicio"]) not in vistas and not vistas.add((a["sala_id"], a["inicio"]))]

    return render_template(
        "reservar.html", ativo="nova", valores=valores, salas=salas,
        grelha=grelha(salas, ocupacao, dia, pedido_grelha), resultado=resultado,
        regras=regras, alternativas=alternativas, salas_por_id=salas_por_id,
        chave=uuid.uuid4().hex, dia=dia, limite=LIMITE_HORAS)


@reservas_bp.route("/reservas")
def minhas():
    reservas, salas, esperas = [], [], []
    try:
        cliente = api()
        reservas = cliente.minhas()
        salas = cliente.salas()
        esperas = cliente.esperas()
    except (ServicoIndisponivel, ErroAPI) as exc:
        flash(str(exc), "erro")
    salas_por_id = {s["id"]: s for s in salas}
    momento = agora()
    em_espera = sorted(
        ({**e, "inicio_dt": para_data(e["janela_inicio"]), "fim_dt": para_data(e["janela_fim"]),
          "duracao_txt": formatar_horas(e["duracao"] / 60)}
         for e in esperas if e["estado"] == "ativa" and para_data(e["janela_fim"]) > momento),
        key=lambda e: e["inicio_dt"])
    proximas, anteriores = [], []
    for r in reservas:
        r = {**r, "inicio_dt": para_data(r["inicio"]), "fim_dt": para_data(r["fim"]),
             "sala_nome": salas_por_id.get(r["sala_id"], {}).get("nome", f"Sala {r['sala_id']}")}
        if r["estado"] == "confirmada" and r["fim_dt"] > momento:
            proximas.append(r)
        else:
            anteriores.append(r)
    proximas.sort(key=lambda r: r["inicio_dt"])
    anteriores.sort(key=lambda r: r["inicio_dt"], reverse=True)
    hoje = momento.date()
    horas_hoje = sum(horas(r["inicio_dt"], r["fim_dt"]) for r in proximas + anteriores
                     if r["estado"] in ("confirmada", "concluida") and r["inicio_dt"].date() == hoje)
    return render_template("minhas.html", ativo="minhas", proximas=proximas, anteriores=anteriores,
                           em_espera=em_espera, horas_hoje=formatar_horas(horas_hoje), limite=LIMITE_HORAS)


@reservas_bp.route("/espera/<int:espera_id>/sair", methods=["POST"])
def sair_espera(espera_id: int):
    try:
        r = api().sair_espera(espera_id)
    except ServicoIndisponivel as exc:
        flash(str(exc), "erro")
        return redirect(url_for("reservas.minhas"))
    if r.ok:
        flash("Saíste da lista de espera.", "ok")
    else:
        flash(r.detalhe, "erro")
    return redirect(url_for("reservas.minhas"))


@reservas_bp.route("/reservas/<int:reserva_id>/qr")
def qr(reserva_id: int):
    try:
        r = api().qr(reserva_id)
        salas = {s["id"]: s for s in api().salas()}
        reserva = next((x for x in api().minhas() if x["id"] == reserva_id), None)
    except (ServicoIndisponivel, ErroAPI) as exc:
        flash(str(exc), "erro")
        return redirect(url_for("reservas.minhas"))
    if not r.ok or reserva is None:
        flash(r.detalhe if not r.ok else "Reserva não encontrada.", "erro")
        return redirect(url_for("reservas.minhas"))
    sala = salas.get(reserva["sala_id"], {"nome": f"Sala {reserva['sala_id']}"})
    return render_template("qr.html", ativo="minhas", reserva=reserva, sala=sala,
                           token=r.dados["token"], expira_em=para_data(r.dados["expira_em"]),
                           check_in_feito=r.dados["check_in_feito"], svg=qr_svg(r.dados["token"]))


@reservas_bp.route("/reservas/<int:reserva_id>/cancelar", methods=["POST"])
def cancelar(reserva_id: int):
    try:
        r = api().cancelar(reserva_id)
    except ServicoIndisponivel as exc:
        flash(str(exc), "erro")
        return redirect(url_for("reservas.minhas"))
    if r.ok:
        flash("Reserva cancelada. O horário ficou livre para outras pessoas.", "ok")
    else:
        flash(r.detalhe, "erro")
    return redirect(url_for("reservas.minhas"))


@reservas_bp.route("/salas")
def salas():
    hoje = agora().date()
    lista, ocupacao = [], []
    try:
        lista = api().salas()
        ocupacao = api().ocupacao(hoje)
    except (ServicoIndisponivel, ErroAPI) as exc:
        flash(str(exc), "erro")
    return render_template("salas.html", ativo="salas", grelha=grelha(lista, ocupacao, hoje), salas=lista,
                           hoje=hoje)


@reservas_bp.route("/estado")
def estado():
    cliente = BookingAPI(current_app.config["BOOKING_API_URL"])
    verificacoes = [
        ("Serviço de reservas", "responde", cliente.vivo("/health/booking/live")),
        ("Serviço de reservas", "base de dados e Redis prontos", cliente.vivo("/health/booking/ready")),
        ("Serviço de autenticação", "responde", cliente.vivo("/health/live")),
    ]
    return render_template("estado.html", ativo="estado", verificacoes=verificacoes, momento=agora())
