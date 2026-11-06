from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    SecretStr,
    field_validator,
)


class RegistoPedido(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    nome: str
    email: EmailStr
    palavra_passe: SecretStr = Field(min_length=10)

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class RegistoResposta(BaseModel):
    utilizador_id: int
    token_confirmacao: str
    uri_configuracao_totp: str


class ConfirmarTOTPRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    token_confirmacao: SecretStr = Field(min_length=43, max_length=128)
    codigo: str = Field(pattern=r"^[0-9]{6}$")


class LoginPedido(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    email: EmailStr
    palavra_passe: SecretStr

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class LoginTOTPRequest(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    token_desafio: SecretStr = Field(min_length=43, max_length=128)
    codigo: str = Field(pattern=r"^[0-9]{6}$")


class DesafioLoginResposta(BaseModel):
    token_desafio: str


class SessaoResposta(BaseModel):
    token: str
    tipo_token: str = "Bearer"
    utilizador_id: int
    email: EmailStr
    perfil: str


class UtilizadorResposta(BaseModel):
    utilizador_id: int
    email: EmailStr
    perfil: str
