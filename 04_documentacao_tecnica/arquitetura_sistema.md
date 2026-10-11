# Arquitetura do sistema — StudySpot

Figuras (em `02_Imagens/`): `img_01.png`. Descrição completa no relatório, capítulo 9.

## Componentes

| Componente | Responsabilidade | Tecnologia | Instâncias |
|---|---|---|---|
| Cliente web | Interface do estudante e do administrador | Streamlit | 1 (objetivo: 2 com `ip_hash`) |
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

## Pontos únicos de falha residuais

| Componente | Mitigação na versão base | Evolução possível |
|---|---|---|
| Nginx | Reinício automático | Segundo Nginx com IP virtual |
| Redis | Reinício automático, reconexão com retry | Redis Sentinel, sessões na base de dados |
| Broker MQTT | Reenvio de eventos pelos dispositivos, modo degradado | Broker redundante |
| PostgreSQL primário | Leituras na réplica, promoção manual documentada | Failover automático (Patroni, repmgr) |
