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
