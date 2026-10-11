# Estrutura da base de dados — StudySpot (PostgreSQL)

## Diagrama entidade-relação

```mermaid
erDiagram
    UTILIZADORES ||--o| SEGREDOS_TOTP : "tem"
    UTILIZADORES ||--o{ CODIGOS_RECUPERACAO : "possui"
    UTILIZADORES ||--o{ CREDENCIAIS_PRESENCA : "usa"
    UTILIZADORES ||--o{ RESERVAS : "faz"
    UTILIZADORES ||--o{ LISTA_ESPERA : "aguarda"
    SALAS ||--o{ RESERVAS : "recebe"
    SALAS ||--o| DISPOSITIVOS : "tem"
    RESERVAS ||--|{ RESERVA_SLOTS : "ocupa"
    SALAS ||--o{ RESERVA_SLOTS : "slots ocupados"

    UTILIZADORES {
        int id PK
        string nome
        string email UK
        string palavra_passe_hash
        string perfil
        bigint ultimo_passo_totp
        boolean ativo
        timestamp criado_em
    }
    SEGREDOS_TOTP {
        int utilizador_id PK, FK
        bytes segredo_cifrado
        bytes nonce
        boolean confirmado
        timestamp criado_em
    }
    CODIGOS_RECUPERACAO {
        int id PK
        int utilizador_id FK
        string hash
        timestamp usado_em
    }
    CREDENCIAIS_PRESENCA {
        int id PK
        int utilizador_id FK
        string tipo
        string valor_hmac UK
    }
    SALAS {
        int id PK
        string nome
        int capacidade
        time abertura
        time fecho
        boolean ativa
    }
    DISPOSITIVOS {
        int id PK
        int sala_id FK
        boolean ativo
    }
    RESERVAS {
        int id PK
        int utilizador_id FK
        int sala_id FK
        timestamp inicio
        timestamp fim
        int n_pessoas
        string estado
        string chave_idempotencia
        timestamp check_in_em
        timestamp criado_em
    }
    RESERVA_SLOTS {
        int reserva_id FK
        int sala_id FK
        timestamp slot_inicio "UNIQUE com sala_id"
    }
    LISTA_ESPERA {
        int id PK
        int utilizador_id FK
        int n_pessoas
        timestamp janela_inicio
        timestamp janela_fim
        int duracao
        timestamp criado_em
        string estado
    }
    EVENTOS_AUDITORIA {
        int id PK
        timestamp quando
        string ator_tipo
        int ator_id
        string tipo
        json detalhe
        string hash_anterior
        string hash
    }
```

## Restrições de integridade

| Tabela | Restrições |
|---|---|
| `utilizadores` | PK `id`; `UNIQUE (email)`; `perfil` ∈ {estudante, administrador} |
| `segredos_totp` | PK/FK `utilizador_id`; o segredo só fica ativo depois de `confirmado` |
| `credenciais_presenca` | `UNIQUE (valor_hmac)`; guarda o HMAC da credencial, não o valor lido |
| `salas` | `capacidade > 0`; `abertura < fecho` |
| `dispositivos` | `UNIQUE (sala_id)` |
| `reservas` | `estado` ∈ {confirmada, concluida, cancelada, libertada}; `UNIQUE (utilizador_id, chave_idempotencia)` |
| `reserva_slots` | **`UNIQUE (sala_id, slot_inicio)`**: garante que não existem duas reservas ativas para o mesmo slot; as linhas são apagadas ao cancelar ou libertar |
| `eventos_auditoria` | Apenas acrescento; encadeamento por hash (evolução) |
