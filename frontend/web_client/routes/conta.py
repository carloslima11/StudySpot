import re

import pyotp
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from models import User, db
from routes.reservas import qr_svg
from services import verificar_codigo
from services.booking_api import BookingAPI, ErroAPI, ServicoIndisponivel

conta_bp = Blueprint("conta", __name__)

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MINIMO_PALAVRA_PASSE = 10


def validar_palavra_passe(nova: str, confirmacao: str) -> str | None:
    if len(nova) < MINIMO_PALAVRA_PASSE:
        return f"A palavra-passe tem de ter pelo menos {MINIMO_PALAVRA_PASSE} caracteres."
    if nova != confirmacao:
        return "As palavras-passe não coincidem."
    return None


def segredo_legivel(segredo: str) -> str:
    return " ".join(segredo[i:i + 4] for i in range(0, len(segredo), 4))


@conta_bp.route("/registo", methods=["GET", "POST"])
def registo():
    if session.get("user_id"):
        return redirect(url_for("reservas.nova"))
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        erro = None
        if not EMAIL.match(email):
            erro = "Escreve um e-mail válido."
        elif User.query.filter_by(email=email).first():
            erro = "Já existe uma conta com este e-mail."
        else:
            erro = validar_palavra_passe(request.form.get("password", ""),
                                         request.form.get("password2", ""))
        if erro:
            flash(erro, "erro")
        else:
            novo = User(email=email)
            novo.set_password(request.form["password"])
            session.clear()
            session["registo"] = {"email": email, "hash": novo.password_hash,
                                  "segredo": pyotp.random_base32()}
            return redirect(url_for("conta.registo_2fa"))
    return render_template("registo.html", email=email)


@conta_bp.route("/registo/2fa", methods=["GET", "POST"])
def registo_2fa():
    pendente = session.get("registo")
    if not pendente:
        return redirect(url_for("conta.registo"))
    if request.method == "POST":
        codigo = request.form.get("codigo", "").replace(" ", "").strip()
        if not verificar_codigo(pendente["segredo"], codigo):
            flash("Código inválido. Confirma a hora do telemóvel e tenta novamente.", "erro")
        elif User.query.filter_by(email=pendente["email"]).first():
            session.pop("registo", None)
            flash("Já existe uma conta com este e-mail.", "erro")
            return redirect(url_for("auth.login"))
        else:
            novo = User(email=pendente["email"], password_hash=pendente["hash"],
                        totp_secret=pendente["segredo"])
            db.session.add(novo)
            db.session.commit()
            session.clear()
            session["user_id"] = novo.id
            flash("Conta criada. Já podes reservar uma sala.", "ok")
            return redirect(url_for("reservas.nova"))
    uri = pyotp.TOTP(pendente["segredo"]).provisioning_uri(name=pendente["email"],
                                                           issuer_name="StudySpot")
    return render_template("registo_2fa.html", svg=qr_svg(uri),
                           segredo=segredo_legivel(pendente["segredo"]), email=pendente["email"])


@conta_bp.route("/perfil", methods=["GET", "POST"])
def perfil():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    utilizador = db.session.get(User, session["user_id"])
    if utilizador is None:
        session.clear()
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        if not utilizador.check_password(request.form.get("atual", "")):
            flash("A palavra-passe atual não está correta.", "erro")
        else:
            erro = validar_palavra_passe(request.form.get("nova", ""), request.form.get("nova2", ""))
            if erro:
                flash(erro, "erro")
            else:
                utilizador.set_password(request.form["nova"])
                db.session.commit()
                flash("Palavra-passe alterada.", "ok")
        return redirect(url_for("conta.perfil"))

    reservas, esperas = [], []
    try:
        cliente = BookingAPI(current_app.config["BOOKING_API_URL"], utilizador.id)
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
    return render_template("perfil.html", ativo="perfil", utilizador=utilizador, contagem=contagem)
