import app as app_module
import routes.auth as rota_auth
import routes.conta as rota_conta
from cachelib import FileSystemCache


class AuthAPIFalsa:
    def registar(self, nome: str, email: str, palavra_passe: str) -> dict[str, str]:
        return {
            "token_confirmacao": "x" * 43,
            "uri_configuracao_totp": (
                "otpauth://totp/StudySpot%3Ateste%40example.com"
                "?secret=ABCDEFGHIJKLMNOP234567&issuer=StudySpot"
            ),
        }

    def confirmar_totp(self, token: str, codigo: str) -> dict[str, str]:
        assert token == "x" * 43
        assert codigo == "123456"
        return {"estado": "confirmado"}

    def iniciar_login(self, email: str, palavra_passe: str) -> dict[str, str]:
        assert email == "teste@example.com"
        assert palavra_passe == "Palavra-passe-de-teste"
        return {"token_desafio": "d" * 43}

    def confirmar_login(self, desafio: str, codigo: str) -> dict[str, object]:
        assert desafio == "d" * 43
        assert codigo == "123456"
        return {
            "token": "s" * 43,
            "utilizador_id": 42,
            "email": "teste@example.com",
            "perfil": "estudante",
        }

    def eu(self, token: str) -> dict[str, object]:
        assert token == "s" * 43
        return {
            "utilizador_id": 42,
            "email": "teste@example.com",
            "perfil": "estudante",
        }

    def logout(self, token: str) -> None:
        assert token == "s" * 43


def criar_cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(rota_auth, "AuthAPI", lambda _url: AuthAPIFalsa())
    monkeypatch.setattr(rota_conta, "AuthAPI", lambda _url: AuthAPIFalsa())
    monkeypatch.setattr(app_module, "AuthAPI", lambda _url: AuthAPIFalsa())
    app = app_module.create_app({
        "TESTING": True,
        "SECRET_KEY": "test-key-not-for-production",
        "SESSION_TYPE": "cachelib",
        "SESSION_CACHELIB": FileSystemCache(cache_dir=str(tmp_path)),
        "SESSION_COOKIE_SECURE": False,
    })
    return app.test_client()


def test_registo_e_confirmacao_totp_usam_auth_service(tmp_path, monkeypatch) -> None:
    client = criar_cliente(tmp_path, monkeypatch)

    resposta = client.post(
        "/registo",
        data={
            "nome": "Utilizador de teste",
            "email": "teste@example.com",
            "password": "Palavra-passe-de-teste",
            "password2": "Palavra-passe-de-teste",
        },
    )
    assert resposta.status_code == 302
    assert resposta.headers["Location"].endswith("/registo/2fa")

    pagina_totp = client.get("/registo/2fa")
    assert pagina_totp.status_code == 200
    assert b"ABCD EFGH IJKL MNOP 2345 67" in pagina_totp.data

    confirmacao = client.post("/registo/2fa", data={"codigo": "123456"})
    assert confirmacao.status_code == 302
    assert confirmacao.headers["Location"].endswith("/login")


def test_login_totp_guarda_token_central_e_logout_revoga(tmp_path, monkeypatch) -> None:
    client = criar_cliente(tmp_path, monkeypatch)

    inicio = client.post(
        "/login",
        data={
            "email": "teste@example.com",
            "password": "Palavra-passe-de-teste",
        },
    )
    assert inicio.status_code == 302
    assert inicio.headers["Location"].endswith("/verificar")

    fim = client.post("/verificar", data={"codigo": "123456"})
    assert fim.status_code == 302
    assert fim.headers["Location"].endswith("/dashboard")

    with client.session_transaction() as sessao:
        assert sessao["token_sessao"] == "s" * 43
        assert sessao["utilizador_id"] == 42

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 302
    assert dashboard.headers["Location"].endswith("/reservar")

    logout = client.post("/logout")
    assert logout.status_code == 302
    with client.session_transaction() as sessao:
        assert "token_sessao" not in sessao


def test_app_nao_arranca_sem_chave_secreta(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(app_module.Config, "SECRET_KEY", None)
    try:
        app_module.create_app({"SESSION_TYPE": "cachelib"})
    except RuntimeError as erro:
        assert str(erro) == "WEB_SECRET_KEY tem de estar configurada."
    else:
        raise AssertionError("A aplicação arrancou sem chave secreta.")
