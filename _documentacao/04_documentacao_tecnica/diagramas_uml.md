# Diagramas UML — StudySpot

Atualizado na 2.ª entrega para refletir o código implementado. As versões da 1.ª entrega estão em `02_imagens/img_02.png` a `img_05.png`; as figuras da 2.ª entrega estão em `img_06.png` (arquitetura), `img_07.png` (sequência da reserva) e `img_08.png` (modelo de dados).

## 1. Diagrama de classes

Classes de domínio (modelos SQLAlchemy) e do motor CSP (`backend/booking_service/app/csp.py`). As classes marcadas como «3.ª entrega» já existem no código, mas a funcionalidade está desligada por omissão.

```mermaid
classDiagram
    class Utilizador {
        +int id
        +string nome
        +string email
        +string palavraPasseHash
        +string perfil
        +int ultimoPassoTotp
        +bool ativo
    }
    class SegredoTOTP {
        +bytes segredoCifrado
        +bytes nonce
        +bool confirmado
    }
    class CodigoRecuperacao {
        +int id
        +string hash
        +datetime usadoEm
    }
    class Sala {
        +int id
        +string nome
        +int capacidade
        +time abertura
        +time fecho
        +bool ativa
    }
    class Reserva {
        +int id
        +int utilizadorId
        +datetime inicio
        +datetime fim
        +int nPessoas
        +string estado
        +string chaveIdempotencia
        +datetime checkInEm
    }
    class ReservaSlot {
        +int salaId
        +datetime slotInicio
    }
    class ListaEspera {
        +int id
        +int utilizadorId
        +int nPessoas
        +datetime janelaInicio
        +datetime janelaFim
        +int duracao
        +string estado
    }
    class Dispositivo {
        +int id
        +bool ativo
    }
    class MotorCSP {
        +ConfigCSP cfg
        +resolver(pedidos, salas, reservasFixas) Resolucao
        +validar(pedido, sala, reservas) Resultado
        +sugerirAlternativas(pedido, salas, reservas) Alternativas
    }
    class ConfigCSP {
        +int slotMinutos = 30
        +float limiteDiarioHoras = 4.0
        +string estrategia = "fifo"
    }
    class Resolucao {
        +dict atribuicoes
        +dict horarios
        +dict rejeitados
        +list listaEspera
    }

    Utilizador "1" --> "0..1" SegredoTOTP : tem
    Utilizador "1" --> "0..*" CodigoRecuperacao : tem
    Utilizador "1" ..> "0..*" Reserva : faz (referência lógica)
    Utilizador "1" ..> "0..*" ListaEspera : aguarda (referência lógica)
    Sala "1" --> "0..*" Reserva : recebe
    Sala "1" --> "0..1" Dispositivo : tem à porta «3.ª entrega»
    Reserva "1" --> "1..*" ReservaSlot : ocupa
    Sala "1" --> "0..*" ReservaSlot : slots ocupados
    MotorCSP --> ConfigCSP
    MotorCSP ..> Resolucao : devolve
    MotorCSP ..> Reserva : atribui
    MotorCSP ..> ListaEspera : reavalia
    note for ReservaSlot "UNIQUE (sala_id, slot_inicio)"
    note for Reserva "UNIQUE (utilizador_id, chave_idempotencia)"
```

A auditoria (`EventoAuditoria`) prevista na 1.ª entrega ainda não está implementada.

## 2. Sequência: login com 2FA

O login tem dois passos. O primeiro valida a palavra-passe e devolve um desafio guardado no Redis; o segundo valida o código TOTP e cria a sessão.

```mermaid
sequenceDiagram
    actor E as Estudante
    participant W as Cliente web
    participant N as Nginx
    participant A as auth1 / auth2
    participant R as Redis
    participant DB as PostgreSQL

    E->>W: Email e palavra-passe (passo 1)
    W->>N: POST /api/auth/login
    N->>A: Encaminha para uma instância
    A->>R: Bloqueado? (5 falhas em 15 min por email e IP)
    A->>DB: Obtém utilizador e segredo TOTP
    A->>A: Verifica o hash Argon2
    alt Palavra-passe válida e TOTP confirmado
        A->>R: Guarda desafio_login:token (expira)
        A-->>W: 202 token_desafio
        W-->>E: Pede o código de 6 dígitos (passo 2)
        E->>W: Código TOTP
        W->>N: POST /api/auth/login/totp
        N->>A: Encaminha (pode ser a outra instância)
        A->>R: Lê e apaga o desafio
        A->>A: Decifra o segredo (AES-GCM) e valida o código
        A->>DB: Rejeita passos iguais ou anteriores a ultimo_passo_totp e guarda o novo
        A->>R: Cria sessao:token (30 min de inatividade, 8 h no máximo)
        A-->>W: Token de sessão
        W->>W: Guarda o token na sessão Flask (Redis)
        W-->>E: Acesso concedido
    else Inválido
        A->>R: Incrementa o contador de falhas
        A-->>W: Erro genérico (ou 429 se bloqueado)
        W-->>E: Credenciais inválidas
    end
```

## 3. Sequência: pedido de reserva

![Sequência da reserva](../02_imagens/img_07.png)

```mermaid
sequenceDiagram
    actor E as Estudante
    participant W as Cliente web
    participant N as Nginx
    participant B as booking1 / booking2
    participant R as Redis
    participant DB as PostgreSQL primário
    participant S as Réplica

    E->>W: POST /reservar (pessoas, dia, início, fim, sala opcional)
    W->>N: POST /api/reservas (Bearer + Idempotency-Key)
    N->>B: Encaminha para uma instância disponível
    B->>R: Valida sessao:token e renova a inatividade
    B->>DB: Já existe reserva com esta chave?
    alt Chave repetida
        B-->>W: 200 duplicada (devolve a reserva existente)
    else Pedido novo
        B->>DB: Lê salas e reservas ativas do dia
        B->>B: Motor CSP escolhe sala e horário
        alt Existe solução
            B->>R: SET NX PX 5000 por (sala, slot), por ordem
            B->>DB: INSERT reserva + slots
            DB->>S: WAL
            S-->>DB: Gravado
            DB-->>B: COMMIT
            B->>R: Liberta os locks
            B-->>W: 201 confirmada
        else Conflito UNIQUE (outro pedido gravou o slot)
            B->>B: Volta ao CSP (até 3 tentativas), depois lista de espera
        else Sem solução
            B->>DB: Guarda em lista_espera (se só faltar vaga)
            B-->>W: 202 espera ou 422 recusada, com motivos e alternativas
        end
    end
    W-->>E: Resultado
```

Respostas possíveis: 201 confirmada, 200 duplicada, 202 espera, 422 recusada, 409 slot bloqueado por outro pedido em curso, 503 Redis indisponível.

## 4. Sequência: check-in por QR Code «3.ª entrega»

Código e testes prontos; ativado com `MQTT_ATIVO=true` e `CHECKIN_SEGREDO`.

```mermaid
sequenceDiagram
    actor E as Estudante
    participant W as Cliente web
    participant B as Serviço de reservas
    participant D as Leitor da porta (dispositivo_qr.py)
    participant M as Broker MQTT
    participant DB as PostgreSQL

    E->>W: "Mostrar QR" na reserva
    W->>B: GET /api/reservas/{id}/qr
    B-->>W: Token assinado HMAC-SHA256 (válido 2 min)
    E->>D: Mostra o QR ao leitor
    D->>M: Publica em studyspot/salas/<sala>/checkin (QoS 1)
    M->>B: Entrega o evento ao subscritor
    B->>B: Valida assinatura, sala e validade
    B->>DB: Regista check_in_em (a partir de 15 min antes do início)
```

## 5. Sequência: libertação automática e realocação «3.ª entrega»

Ativada com `TAREFA_PERIODICA_ATIVA=true`; corre a cada 60 s em cada instância de reservas.

```mermaid
sequenceDiagram
    participant T as Tarefa periódica (booking)
    participant DB as PostgreSQL
    participant C as MotorCSP
    participant R as Redis

    T->>T: Broker MQTT saudável? Se não, salta o ciclo
    T->>DB: Reservas sem check-in 15 min após o início (FOR UPDATE SKIP LOCKED)
    T->>DB: Marca como libertadas e apaga os slots
    T->>DB: Lê a lista de espera ativa (janelas truncadas ao próximo bloco)
    T->>C: Resolve todos os pedidos em espera, por ordem de chegada
    C-->>T: Nova atribuição
    T->>R: Locks dos slots
    T->>DB: Grava a reserva com a chave espera-<id> (UNIQUE sala e slot)
    T->>DB: Marca o pedido como atendido
```

O `FOR UPDATE SKIP LOCKED` permite que as duas instâncias corram o ciclo ao mesmo tempo sem libertar a mesma reserva duas vezes, e a chave `espera-<id>` impede que repetir o ciclo duplique reservas.
