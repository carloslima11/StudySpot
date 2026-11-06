# Guião de teste de tolerância a falhas

Este guião testa a redundância das instâncias de aplicação e a replicação síncrona do PostgreSQL no Docker Compose local. Não apaga volumes nem dados. Executar na raiz do repositório, com o Docker Desktop ativo.

> **Limite importante:** `auth1`/`auth2` e `booking1`/`booking2` são pares de instâncias equivalentes, sem primário e secundário. Só o PostgreSQL tem um primário (`postgres`) e uma réplica (`postgres-replica`). A réplica PostgreSQL é síncrona, mas não há failover automático nem encaminhamento dos serviços para a réplica. **Não pares nem mates o primário PostgreSQL** à espera que a réplica assuma o serviço. Este guião testa a falha de uma instância de aplicação de cada vez e, separadamente, a indisponibilidade da réplica.

## 1. Preparação

Abrir três terminais na raiz do repositório.

No **Terminal 1**, arrancar a aplicação, as dependências e o serviço que ativa a replicação síncrona:

```bash
docker compose --env-file backend/auth_service/.env up -d postgres postgres-replica postgres-enable-sync redis auth1 auth2 booking1 booking2 nginx web
docker compose --env-file backend/auth_service/.env ps
```

Esperar que `postgres`, `postgres-replica`, `redis`, `auth1`, `auth2`, `booking1` e `booking2` estejam saudáveis. O serviço `postgres-enable-sync` deve terminar com código 0; o serviço `web` pode não ter healthcheck, por isso confirmar que está `Up`.

No **Terminal 2**, abrir os logs:

```bash
docker compose --env-file backend/auth_service/.env logs -f --tail=50 nginx web auth1 auth2 booking1 booking2 postgres postgres-replica
```

Deixar este terminal aberto. `Ctrl+C` termina apenas a visualização dos logs, não os containers.

No **Terminal 3**, confirmar os endpoints através do Nginx e o estado síncrono:

```bash
curl -i http://127.0.0.1:8080/health/ready
curl -i http://127.0.0.1:8080/health/booking/ready
docker compose --env-file backend/auth_service/.env exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
docker compose --env-file backend/auth_service/.env exec -T postgres-replica sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pg_is_in_recovery();"'
```

Esperado: os dois health checks devolvem `200`; a réplica aparece como `streaming` e `sync`; `pg_is_in_recovery()` devolve `t`. As portas do Nginx estão publicadas em `127.0.0.1`, por isso os testes são locais à máquina.

Abrir a interface em `https://localhost:8443` e iniciar sessão com uma conta de teste. A ligação HTTPS usa o certificado local `mkcert`; o browser tem de confiar na CA local e o certificado deve ser válido para `localhost`. Se for necessário criar uma conta, o registo já usa o serviço central de autenticação; a conta ficará persistida na base de dados partilhada.

## 2. Falha de uma instância de autenticação

No **Terminal 3**, parar apenas uma instância:

```bash
docker compose --env-file backend/auth_service/.env stop auth1
```

Na interface, fazer uma operação de autenticação que possa ser repetida sem efeitos indesejados. Em paralelo, confirmar que o Nginx continua a responder através do health check:

```bash
curl -i http://127.0.0.1:8080/health/live
```

Esperado: o serviço `auth2` continua a responder. Nos logs, confirmar que os pedidos seguintes chegam a `auth2`. Pode existir uma falha inicial enquanto o Nginx deteta que `auth1` deixou de responder; o balanceamento configurado é passivo.

Recuperar a instância:

```bash
docker compose --env-file backend/auth_service/.env start auth1
docker compose --env-file backend/auth_service/.env ps auth1 auth2
```

Esperar até `auth1` ficar saudável antes de continuar.

## 3. Falha de uma instância de reservas

Na interface, confirmar que é possível consultar salas ou reservas. Depois, no **Terminal 3**:

```bash
docker compose --env-file backend/auth_service/.env stop booking1
```

Repetir uma consulta na interface e confirmar que o serviço de reservas continua disponível. O health check público de reservas é:

```bash
curl -i http://127.0.0.1:8080/health/booking/live
```

Esperado: `booking2` continua a responder e os logs mostram os pedidos a chegar a essa instância. Não submeter várias reservas apenas para gerar tráfego; uma consulta é suficiente.

Recuperar:

```bash
docker compose --env-file backend/auth_service/.env start booking1
docker compose --env-file backend/auth_service/.env ps booking1 booking2
```

Esperar até `booking1` ficar saudável.

## 4. Teste seguro da réplica síncrona

Este teste **pára a réplica, não o primário**. Antes de parar, confirmar novamente `sync_state = sync`:

```bash
docker compose --env-file backend/auth_service/.env exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
```

Parar a réplica:

```bash
docker compose --env-file backend/auth_service/.env stop postgres-replica
```

Na interface, fazer apenas uma operação de escrita de teste, se houver uma conta e um pedido de teste já preparados. Esperado: a escrita não é confirmada sem a réplica e termina com erro `503` após o limite configurado; as leituras no primário podem continuar. Não repetir automaticamente o pedido.

Voltar a iniciar a réplica:

```bash
docker compose --env-file backend/auth_service/.env start postgres-replica
```

Esperar que fique saudável e confirmar que o primário voltou a mostrar `streaming` e `sync`:

```bash
docker compose --env-file backend/auth_service/.env ps postgres postgres-replica
docker compose --env-file backend/auth_service/.env exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
```

## 5. Falha do primário PostgreSQL: o que ainda não testar

**Não executar `docker compose stop postgres`, `docker stop` nem `docker kill` no primário como teste de failover automático.** Os serviços continuam configurados para ligar ao hostname `postgres`, e não existe Patroni, proxy de encaminhamento ou promoção automática. Se o primário parar, os pedidos que usam a BD falham; a réplica não passa a receber automaticamente o tráfego dos serviços. Não promover a réplica manualmente durante este guião.

O teste automático de promoção só deve ser acrescentado depois de implementar e validar um gestor de failover e um endpoint estável para os serviços encontrarem o primário. Até lá, a demonstração correta é: falha da instância de aplicação → outra instância atende; falha da réplica → escritas falham em segurança; falha do primário → indisponibilidade até recuperação manual.

## 6. Reposição e registo dos resultados

No **Terminal 3**, garantir que as instâncias paradas voltam a arrancar:

```bash
docker compose --env-file backend/auth_service/.env start auth1 booking1 postgres-replica
docker compose --env-file backend/auth_service/.env ps
```

Confirmar novamente os dois health checks da secção 1 e `sync_state = sync`. Registar para a demonstração quais pedidos continuaram disponíveis, se houve erro inicial do Nginx, o tempo aproximado de recuperação e a diferença entre falha de aplicação e falha da BD.

> Não executar `docker compose down -v`: a opção `-v` remove volumes e pode apagar dados.
