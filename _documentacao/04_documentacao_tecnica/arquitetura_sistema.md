# Arquitetura do sistema — StudySpot

Figuras (em `02_Imagens/`): `img_01.png`. Descrição completa no relatório, capítulo 9.

## Componentes

| Componente | Responsabilidade | Tecnologia | Instâncias |
|---|---|---|---|
| Cliente web | Interface do estudante e do administrador | Flask + Gunicorn | 1 |
| Nginx | Ponto de entrada, balanceamento, TLS | Nginx | 1 |
| Serviço de autenticação | Registo, login, TOTP, sessões | Python, FastAPI | 2 ou mais |
| Serviço de reservas | Salas, reservas, CSP, lista de espera, libertação | Python, FastAPI | 2 ou mais |
| PostgreSQL | Dados persistentes | PostgreSQL | 1 primário + 1 réplica |
| Redis | Sessões, locks, contadores de tentativas | Redis | 1 |
| Broker MQTT | Eventos de check-in | Eclipse Mosquitto | 1 |
| Dispositivos IoT | Leitura RFID/QR e publicação de eventos | ESP32 (real ou simulado) | N |

## Princípios

1. Serviços sem estado: qualquer instância atende qualquer pedido;
2. Redundância por camada (cliente, serviços, dados);
3. Falha segura: sem garantia de correção, a operação é recusada de forma explícita;
4. A base de dados é a fonte de verdade da consistência, o Redis é uma otimização.

## Consistência das reservas

Lock distribuído por slot (Redis) + restrição `UNIQUE (sala_id, slot_inicio)` na tabela `reserva_slots` (garantia de correção) + chave de idempotência em cada pedido.

A réplica PostgreSQL recebe WAL por *streaming* síncrono. As escritas só são confirmadas depois de a réplica gravar o WAL; se a réplica estiver indisponível, as escritas falham após o limite de tempo configurado. A aplicação continua ligada ao primário nesta fase; o encaminhamento de leituras para a réplica e o failover automático não estão implementados.

A palavra-passe exclusiva da role de replicação é guardada em `POSTGRES_REPLICATION_PASSWORD` no ficheiro local ignorado pelo Git (`backend/auth_service/.env`). Deve ser gerada aleatoriamente e nunca incluída no repositório.

O cliente web Flask não tem uma base de dados de utilizadores própria. O serviço de autenticação valida palavra-passe e TOTP, mantém sessões opacas em Redis e partilha o respetivo token com o serviço de reservas. O navegador só comunica com o Nginx por HTTPS; o web client comunica com as APIs através da rede interna do Compose.

## Pontos únicos de falha residuais

| Componente | Mitigação na versão base | Evolução possível |
|---|---|---|
| Nginx | Reinício automático | Segundo Nginx com IP virtual |
| Redis | Reinício automático, reconexão com retry | Redis Sentinel, sessões na base de dados |
| Broker MQTT | Reenvio de eventos pelos dispositivos, modo degradado | Broker redundante |
| PostgreSQL primário | Réplica síncrona; promoção manual e alteração do destino das ligações | Failover automático (Patroni, repmgr) |
