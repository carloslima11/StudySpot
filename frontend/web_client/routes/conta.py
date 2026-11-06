from urllib.parse import parse_qs, urlparse
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from routes.reservas import qr_svg
from services.auth_api import AuthAPI, AuthAPIError, AuthServiceUnavailable
from services.booking_api import BookingAPI, ErroAPI, ServicoIndisponivel

conta_bp = Blueprint("conta", __name__)

MINIMO_PALAVRA_PASSE = 10


def segredo_legivel(segredo: str) -> str:
    return " ".join(segredo[i:i + 4] for i in range(0, len(segredo), 4))


def auth_api() -> AuthAPI:
    return AuthAPI(current_app.config["AUTH_API_URL"])


@conta_bp.route("/registo", methods=["GET", "POST"])
def registo():
    if session.get("token_sessao"):
        return redirect(url_for("reservas.nova"))
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        nome = request.form.get("nome", "").strip()
        erro = None
        if not nome:
            erro = "Escreve o teu nome."
        palavra_passe = request.form.get("password", "")
        if not erro and len(palavra_passe) < MINIMO_PALAVRA_PASSE:
            erro = f"A palavra-passe tem de ter pelo menos {MINIMO_PALAVRA_PASSE} caracteres."
        if not erro and palavra_passe != request.form.get("password2", ""):
            erro = "As palavras-passe não coincidem."
        if erro:
            flash(erro, "erro")
        else:
            try:
                dados = auth_api().registar(
                    nome,
                    email,
                    palavra_passe,
                )
                session.clear()
                session["registo_pendente"] = {
                    "email": email,
                    "token_confirmacao": dados["token_confirmacao"],
                    "uri_configuracao_totp": dados["uri_configuracao_totp"],
                }
                return redirect(url_for("conta.registo_2fa"))
            except AuthAPIError as exc:
                flash(str(exc), "erro")
            except AuthServiceUnavailable as exc:
                flash(str(exc), "erro")
    return render_template("registo.html", email=email)


@conta_bp.route("/registo/2fa", methods=["GET", "POST"])
def registo_2fa():
    pendente = session.get("registo_pendente")
    if not pendente:
        return redirect(url_for("conta.registo"))
    if request.method == "POST":
        codigo = request.form.get("codigo", "").replace(" ", "").strip()
        try:
            auth_api().confirmar_totp(pendente["token_confirmacao"], codigo)
            session.clear()
            flash(
                "Conta criada. Inicia sessão com o próximo código da app autenticadora.",
                "ok",
            )
            return redirect(url_for("auth.login"))
        except AuthAPIError as exc:
            flash(str(exc), "erro")
        except AuthServiceUnavailable as exc:
            flash(str(exc), "erro")
    uri = pendente["uri_configuracao_totp"]
    segredo = parse_qs(urlparse(uri).query).get("secret", [""])[0]
    return render_template("registo_2fa.html", svg=qr_svg(uri),
                           segredo=segredo_legivel(segredo), email=pendente["email"])


@conta_bp.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not session.get("token_sessao"):
        return redirect(url_for("auth.login"))

    reservas, esperas = [], []
    try:
        cliente = BookingAPI(
            current_app.config["BOOKING_API_URL"],
            session["token_sessao"],
        )
        reservas = cliente.minhas()
        esperas = cliente.esperas()
    except (ServicoIndisponivel, ErroAPI) as exc:
        flash(str(exc), "erro")
    contagem = {
        "confirmadas": sum(r["estado"] == "confirmada" for r in reservas),
        "concluidas": sum(r["estado"] == "concluida" for r in reservas),
        "libertadas": sum(r["estado"] == "libertada" for r in reservas),
        "espera": sum(e["estado"] == "ativa" for e in esperas),
    }
    utilizador = {"email": session.get("utilizador_email", "")}
    return render_template("perfil.html", ativo="perfil", utilizador=utilizador, contagem=contagem)
