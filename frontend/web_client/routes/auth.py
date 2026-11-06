from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask import current_app

from services.auth_api import AuthAPI, AuthAPIError, AuthServiceUnavailable

auth_bp = Blueprint("auth", __name__)


def api() -> AuthAPI:
    return AuthAPI(current_app.config["AUTH_API_URL"])


@auth_bp.route("/", methods=["GET"])
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        try:
            desafio = api().iniciar_login(email, request.form.get("password", ""))
            session.clear()
            session["desafio_login"] = desafio["token_desafio"]
            return redirect(url_for("auth.verificar"))
        except AuthAPIError as exc:
            flash(str(exc), "erro")
        except AuthServiceUnavailable as exc:
            flash(str(exc), "erro")

    return render_template("login.html")


@auth_bp.route("/verificar", methods=["GET", "POST"])
def verificar():
    desafio = session.get("desafio_login")
    if not desafio:
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").replace(" ", "").strip()
        try:
            dados = api().confirmar_login(desafio, codigo)
            session.clear()
            session["token_sessao"] = dados["token"]
            session["utilizador_id"] = dados["utilizador_id"]
            session["utilizador_email"] = dados["email"]
            session["perfil"] = dados["perfil"]
            session.permanent = True
            return redirect(url_for("auth.dashboard"))
        except AuthAPIError as exc:
            flash(str(exc), "erro")
        except AuthServiceUnavailable as exc:
            flash(str(exc), "erro")

    return render_template("verificar.html")


@auth_bp.route("/dashboard")
def dashboard():
    if not session.get("token_sessao"):
        return redirect(url_for("auth.login"))
    return redirect(url_for("reservas.nova"))


@auth_bp.route("/logout", methods=["POST"])
def logout():
    token = session.get("token_sessao")
    if token:
        try:
            api().logout(token)
        except AuthServiceUnavailable:
            flash(
                "A sessão local foi terminada, mas o serviço de autenticação não confirmou o logout.",
                "erro",
            )
    session.clear()
    return redirect(url_for("auth.login"))