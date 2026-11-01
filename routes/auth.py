from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from models import User
from services import verificar_codigo

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET"])
def index():
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):
            # Passo 1 concluído: guarda o utilizador "pendente" até validar o 2FA
            session.clear()
            session["pending_user_id"] = user.id
            session["remember"] = bool(request.form.get("remember"))
            return redirect(url_for("auth.verificar"))

        flash("E-mail ou palavra-passe incorretos.", "erro")

    return render_template("login.html")


@auth_bp.route("/verificar", methods=["GET", "POST"])
def verificar():
    user_id = session.get("pending_user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = User.query.get(user_id)

    if request.method == "POST":
        codigo = request.form.get("codigo", "").replace(" ", "").strip()
        if verificar_codigo(user.totp_secret, codigo):
            session.pop("pending_user_id", None)
            session["user_id"] = user.id
            session.permanent = session.pop("remember", False)
            return redirect(url_for("auth.dashboard"))
        flash("Código inválido. Tenta novamente.", "erro")

    return render_template("verificar.html")


@auth_bp.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))
    return "<h1>Login completo ✅</h1><a href='/logout'>Sair</a>"


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))