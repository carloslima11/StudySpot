from typing import Any

import requests


class AuthAPIError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code


class AuthServiceUnavailable(Exception):
    pass


class AuthAPI:
    def __init__(self, base_url: str, timeout: float = 5.0) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    def _pedido(
        self,
        metodo: str,
        caminho: str,
        *,
        token: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        cabecalhos = dict(kwargs.pop("headers", {}))
        if token:
            cabecalhos["Authorization"] = f"Bearer {token}"
        try:
            resposta = requests.request(
                metodo,
                f"{self.base}{caminho}",
                headers=cabecalhos,
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise AuthServiceUnavailable(
                "O serviço de autenticação está temporariamente indisponível."
            ) from exc

        if resposta.status_code in (502, 503, 504):
            raise AuthServiceUnavailable(
                "O serviço de autenticação está temporariamente indisponível."
            )
        if resposta.status_code == 204:
            return {}
        try:
            dados = resposta.json()
        except ValueError:
            dados = {}
        if not resposta.ok:
            detalhe = dados.get("detail") if isinstance(dados, dict) else None
            raise AuthAPIError(
                resposta.status_code,
                detalhe if isinstance(detalhe, str) else "O pedido não foi aceite.",
            )
        return dados if isinstance(dados, dict) else {}

    def registar(self, nome: str, email: str, palavra_passe: str) -> dict[str, Any]:
        return self._pedido(
            "POST",
            "/registo",
            json={
                "nome": nome,
                "email": email,
                "palavra_passe": palavra_passe,
            },
        )

    def confirmar_totp(self, token: str, codigo: str) -> dict[str, Any]:
        return self._pedido(
            "POST",
            "/totp/confirmar",
            json={"token_confirmacao": token, "codigo": codigo},
        )

    def iniciar_login(self, email: str, palavra_passe: str) -> dict[str, Any]:
        return self._pedido(
            "POST",
            "/login",
            json={"email": email, "palavra_passe": palavra_passe},
        )

    def confirmar_login(self, desafio: str, codigo: str) -> dict[str, Any]:
        return self._pedido(
            "POST",
            "/login/totp",
            json={"token_desafio": desafio, "codigo": codigo},
        )

    def eu(self, token: str) -> dict[str, Any]:
        return self._pedido("GET", "/eu", token=token)

    def logout(self, token: str) -> None:
        self._pedido("POST", "/logout", token=token)
