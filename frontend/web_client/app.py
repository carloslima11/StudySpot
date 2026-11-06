import logging
from collections.abc import Mapping
from typing import Any

from flask import Flask, abort, flash, redirect, request, session, url_for
from flask_session import Session
from redis.exceptions import RedisError
from werkzeug.exceptions import HTTPException

from config import Config
from routes.auth import auth_bp
from routes.conta import conta_bp
from routes.reservas import reservas_bp
from services.auth_api import AuthAPI, AuthAPIError, AuthServiceUnavailable

logger = logging.getLogger(__name__)


def create_app(config_overrides: Mapping[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("WEB_SECRET_KEY tem de estar configurada.")

    Session(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(conta_bp)
    app.register_blueprint(reservas_bp)

    @app.before_request
    def validar_sessao_central():
        token = session.get("token_sessao")
        if not token or request.endpoint in {"auth.logout", "static"}:
            return None
        try:
            utilizador = AuthAPI(app.config["AUTH_API_URL"]).eu(token)
        except AuthAPIError as exc:
            if exc.status_code == 401:
                session.clear()
                flash("A sessão expirou. Inicia sessão novamente.", "erro")
                return redirect(url_for("auth.login"))
            abort(503)
        except AuthServiceUnavailable:
            abort(503)
        session["utilizador_id"] = utilizador["utilizador_id"]
        session["utilizador_email"] = utilizador["email"]
        session["perfil"] = utilizador["perfil"]
        return None

    @app.errorhandler(503)
    def servico_indisponivel(erro: HTTPException) -> tuple[str, int]:
        logger.warning("Pedido web indisponível: %s", erro.name)
        return (
            "O serviço está temporariamente indisponível. "
            "Tenta novamente dentro de instantes.",
            503,
        )

    @app.errorhandler(RedisError)
    def redis_indisponivel(_erro: RedisError) -> tuple[str, int]:
        logger.warning("Pedido web indisponível: falha no Redis.")
        return (
            "O serviço está temporariamente indisponível. "
            "Tenta novamente dentro de instantes.",
            503,
        )

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
