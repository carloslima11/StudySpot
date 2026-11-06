# Modelo de Faltas – StudySpot

O procedimento passo-a-passo para executar os ensaios locais está no [Guião de teste de tolerância a falhas](./guiao_teste_tolerancia_falhas.md).

## 1. Objetivo

O presente documento define o modelo de faltas do sistema de reserva de salas de estudo, identificando os componentes que podem falhar, os tipos de falha considerados, o número de falhas simultâneas que o sistema pretende suportar e os mecanismos de deteção e recuperação associados.

Nesta primeira fase do projeto, o objetivo não é apresentar a implementação definitiva da tolerância a falhas, mas sim estabelecer que falhas o sistema pretende suportar e que garantias oferece perante cada uma. Este modelo será a base para a implementação e para os testes experimentais de tolerância a falhas nas entregas seguintes.

## 2. Visão geral da arquitetura

O sistema é composto pelos seguintes componentes:

- **Web client**: interface do utilizador;
- **Nginx**: load balancer / reverse proxy;
- **Serviços de autenticação**: registo, login, 2FA (TOTP);
- **Serviços de reservas**: gestão de salas, CSP, reservas;
- **PostgreSQL**: utilizadores, segredos TOTP, salas, reservas;
- **Redis**: sessões partilhadas e locks distribuídos;
- **Broker MQTT**: eventos de check-in/check-out dos dispositivos IoT (ESP32 ou simulados).

Todos os componentes correm em containers Docker, geridos através de Docker Compose.

## 3. Componentes suscetíveis a falhas

Os componentes que são suscetíveis a falhas são os seguintes:

| Componente | Função | Risco principal |
|---|---|---|
| Web client | Interface do utilizador | Perda de sessão, timeout de WebSocket |
| Nginx | Distribui tráfego pelas instâncias | Ponto único de falha se não for também redundante |
| Serviços de autenticação | Login e 2FA | Indisponibilidade de uma instância |
| Serviços de reservas | Reservas e CSP | Indisponibilidade de uma instância, resultados inconsistentes do CSP |
| PostgreSQL | Armazenamento persistente | Falha do primary, divergência entre réplicas |
| Redis | Sessões e locks | Perda de locks ativos, perda de sessões |
| Broker MQTT | Eventos de check-in | Perda de eventos, desligamento do broker |
| Containers Docker | Execução de cada serviço | Crash do processo, reinício inesperado |

## 4. Tipos de falhas consideradas

### 4.1. Falha de um container

Um container pode parar por erro da aplicação, encerramento inesperado ou falta de recursos no ambiente de execução.

### 4.2. Falha de uma instância de serviço

Uma instância dos serviços de autenticação ou dos serviços de reservas pode ficar indisponível ou deixar de responder.

### 4.3. Falha da base de dados

Se o PostgreSQL primário ficar indisponível, os serviços perdem o acesso à base de dados até à promoção manual da réplica e à alteração do destino das ligações. A réplica pode ser consultada diretamente, mas os serviços ainda não encaminham leituras para ela. Não existe failover automático.

### 4.4. Falha de uma réplica

A réplica do PostgreSQL pode ficar indisponível. O primário mantém as leituras, mas as escritas ficam bloqueadas pela replicação síncrona e falham após o limite de cinco segundos, com resposta HTTP 503. Não se confirma uma escrita sem a respetiva gravação na réplica.

### 4.5. Falha do Redis

O Redis pode ficar indisponível, afetando sessões ativas e locks distribuídos em curso.

### 4.6. Falha de comunicação

Pode ocorrer interrupção ou perda temporária de comunicação entre dois componentes (ex: serviços de reservas ↔ Postgres, Nginx ↔ instâncias).

### 4.7. Falha do broker MQTT

O broker pode ficar indisponível, impedindo a receção de eventos de check-in dos dispositivos IoT.

### 4.8. Perda temporária de conectividade

Um componente pode permanecer ativo, mas inacessível, devido a problemas de rede.

## 5. Número de falhas simultâneas suportadas

O sistema deverá suportar a falha de **um componente individual de cada tipo em simultâneo**, desde que exista redundância disponível para esse componente:

- 1 instância dos **serviços de autenticação** em baixo- a outra assume;
- 1 instância dos **serviços de reservas** em baixo- a outra assume;
- O **PostgreSQL primário** em baixo- a réplica assume leitura, a escrita fica condicionada ao mecanismo de failover;
- O **Redis** em baixo- as sessões ativas são perdidas e o login e a criação de reservas ficam indisponíveis até o Redis ser reiniciado (falha segura, com mensagem clara ao utilizador); as reservas já confirmadas não são afetadas (ver secções 9 e 10).

**Não é assumido**, nesta fase, que o sistema suporta a falha simultânea de **todas** as instâncias do mesmo serviço (ex: as duas instâncias dos serviços de autenticação em baixo ao mesmo tempo), nem a falha simultânea do primário e da réplica do PostgreSQL. O número exato de falhas simultâneas suportadas por componente será reavaliado após a arquitetura final e o número de réplicas estarem implementados.

## 6. Funcionalidades que permanecem disponíveis

As funcionalidades que permanecem disponíveis mesmo depois de alguma falha são:

| Falha | Funcionalidades que continuam disponíveis | Funcionalidades afetadas |
|---|---|---|
| 1 instância dos serviços de autenticação | Login, registo, verificação 2FA (via outra instância). | Nenhuma, desde que o Nginx redirecione corretamente. |
| 1 instância dos serviços de reservas | Consulta e criação de reservas (via outra instância). | Nenhuma, idem. |
| PostgreSQL primário | Leituras (via réplica, se configurada como read replica). | Escritas (novas reservas, novos registos) até ao failover. |
| Redis | Dados persistentes intactos (reservas confirmadas e utilizadores). | Sessões ativas, login e criação de reservas, até ao reinício do Redis. |
| Broker MQTT | Reservas e login continuam a funcionar normalmente | Check-in automático, libertação automática de salas fica suspensa até o broker recuperar. |

O sistema deve privilegiar, sempre que uma operação não possa ser confirmada com garantias suficientes, **recusar a operação de forma explícita** em vez de arriscar um estado inconsistente, por exemplo, não confirmar uma reserva se o lock do Redis ou a escrita no Postgres não puderem ser garantidos.

## 7. Deteção de falhas

Os seguintes mecanismos serão utilizados para detetar falhas nos diferentes componentes:

- **Health checks** do Docker/Nginx, para verificar periodicamente se uma instância responde;
- **Timeouts** nas chamadas entre serviços (ex: serviços de reservas → Postgres, serviços de reservas → Redis);
- **Deteção de ausência de resposta** (conexão recusada, timeout de ligação);
- **Monitorização do estado dos containers**;
- **Logs** centralizados, para registar e correlacionar eventos de falha;
- **Heartbeat** do broker MQTT, para detetar a perda de ligação dos publishers/subscribers.

Quando uma falha é detetada, o Nginx deve deixar de encaminhar pedidos para a instância afetada, e o componente afetado deve ser assinalado nos logs para investigação.

## 8. Recuperação e substituição

- **Reinício automático do container** para instâncias dos serviços de autenticação, serviços de reservas e broker MQTT;
- **Failover do PostgreSQL**: a promoção da réplica a primária e a alteração do destino das ligações dos serviços são manuais nesta fase do projeto; não há failover automático;
- **Reconexão automática ao Redis e ao broker MQTT**, com lógica de retry no lado dos serviços;
- **Re-sincronização da réplica do PostgreSQL** após recuperação, para voltar a receber as atualizações do primário.

Após a recuperação, o componente volta a integrar a arquitetura e a redundância é restabelecida.

## 9. Perda de informação possível

A integridade dos dados é um requisito central, especialmente para reservas já confirmadas. Deve ser evitada a seguinte situação:

> O utilizador submete uma reserva → o sistema indica que foi confirmada → ocorre uma falha → a reserva não fica persistida.

Para prevenir isto:

- Uma reserva só é confirmada ao utilizador depois de o lock do Redis e a escrita no PostgreSQL serem bem-sucedidos;
- É usada uma **chave de idempotência** (Idempotency-Key) nos pedidos de criação de reserva, para que um reenvio causado por timeout de rede não crie uma reserva duplicada, o servidor reconhece o pedido repetido e devolve o resultado anterior em vez de criar uma entrada nova;
- Se o resultado de uma operação for desconhecido (ex: timeout a meio do pedido), a interface consulta o estado atual antes de permitir nova tentativa, em vez de reenviar às cegas.

Dados que não podem ser perdidos: reservas confirmadas, dados dos utilizadores, segredos TOTP. Dados que podem ser perdidos sem impacto crítico: estado do ecrã, sessão ativa, formulário por preencher.

## 10. Consistência de dados entre réplicas

Para a réplica do PostgreSQL, é usada replicação em *streaming* síncrona. Com `synchronous_commit=on`, o primário só confirma uma transação depois de a réplica gravar o respetivo WAL. Assim, uma transação confirmada pode ser recuperada promovendo esta réplica. Se a réplica falhar, as escritas no primário não são confirmadas e terminam com erro após cinco segundos; as leituras no primário continuam disponíveis. A recuperação da réplica restabelece a redundância. A promoção continua manual e esta replicação não substitui backups.

Para o Redis, a principal preocupação de consistência é o **lock distribuído** usado para evitar reservas duplicadas. Se o Redis falhar a meio de uma operação de lock, a reserva não deve ser confirmada apenas com base nesse lock. Por isso, é adicionada uma **constraint UNIQUE (sala, horário)** na tabela de reservas do PostgreSQL, como segunda barreira, mesmo que o lock falhe ou seja perdido, a base de dados rejeita qualquer tentativa de reserva duplicada.

Esta combinação (lock distribuído + constraint na BD) garante que, mesmo com falha de um dos dois mecanismos, não existe inconsistência entre o que o sistema mostra como reservado e o que está realmente na base de dados.

## 11. Falhas específicas da interface

O web client é construído com Flask e Gunicorn. As sessões do navegador são guardadas no Redis, e não numa cookie com os dados de autenticação. Nesta versão existe uma instância do web client; se forem adicionadas várias instâncias, todas devem usar o mesmo Redis e a mesma chave `WEB_SECRET_KEY`:

- Não é necessária afinidade de sessão enquanto o armazenamento partilhado no Redis estiver disponível;
- Nesta fase do projeto, existe uma única instância do web client, documentada como ponto único de falha.

**Comportamento perante falhas, do ponto de vista do utilizador:**

| Situação | Comportamento esperado |
|---|---|
| Um serviço devolve erro 503 | Mensagem simples: “O serviço está temporariamente indisponível. Tenta novamente dentro de instantes.” |
| Timeout ao criar reserva | A interface não reenvia automaticamente; consulta primeiro “As minhas reservas” para confirmar se a reserva já foi criada. |
| Perda de sessão | Utilizador é reencaminhado para o login, com explicação simples do motivo, dados já confirmados pelo sistema não são afetados. |
| Reserva recusada | Explicação do motivo e, sempre que possível, horários alternativos. |

As mensagens de erro seguem três princípios:

- Linguagem simples (sem códigos técnicos desnecessários);
- Explicação do que aconteceu;
- Indicação do próximo passo possível.

O erro técnico original continua a ser registado nos logs internos para efeitos de manutenção.

## 12. Cenários de teste de tolerância a falhas

Os seguintes cenários serão testados experimentalmente nas entregas seguintes, desligando componentes propositadamente:

| Cenário | O que se testa |
|---|---|
| Paragem do docker numa instância de serviços de autenticação | A outra instância continua a responder, o Nginx deixa de encaminhar para a instância parada. |
| Paragem do docker numa instância de serviços de reserva | Idem, para reservas. |
| Tornar a réplica do PostgreSQL indisponível | Leituras continuam no primário; escritas devolvem 503 após cinco segundos, sem confirmar alterações sem réplica. |
| Tornar o PostgreSQL primário indisponível | Serviços devolvem 503 até promoção manual e alteração do destino das ligações; a réplica não é usada automaticamente para leituras. |
| Paragem do docker no Redis | Login e criação de reservas indisponíveis, com mensagem clara ao utilizador; reservas confirmadas intactas, após o reinício, o serviço retoma sem reservas duplicadas. |
| Desligar o broker MQTT | Login e reservas continuam a funcionar, check-in automático fica suspenso até o broker voltar. |
| Interromper a comunicação entre dois serviços | A falha é detetada (timeout/health check) e o comportamento documentado nas secções 6 e 8 é verificado. |

Para cada cenário, será registado o componente que falhou, como foi detetado, funcionalidades que permaneceram disponíveis, impacto para o utilizador, eventual perda de informação, mecanismo de recuperação, e restabelecimento da redundância.

## 13. Resumo

O modelo de faltas estabelece que os componentes individuais do sistema podem falhar isoladamente, sem que isso provoque a indisponibilidade total da plataforma, desde que exista redundância disponível para o componente em causa. A tolerância a faltas assenta em múltiplas instâncias dos serviços de aplicação, replicação do PostgreSQL, deteção ativa através de health checks e timeouts, e mecanismos de recuperação automática (reinício de containers) ou semiautomática (failover de base de dados).

A proteção da integridade dos dados, em particular das reservas confirmadas, é garantida pela combinação de locks distribuídos no Redis com uma constraint UNIQUE na base de dados, e pelo uso de chaves de idempotência para evitar duplicação em caso de reenvio de pedidos.