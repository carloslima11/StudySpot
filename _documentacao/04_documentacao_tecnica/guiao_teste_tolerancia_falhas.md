# Guião de teste de tolerância a falhas

Atualizado na 2.ª entrega. Este guião testa a redundância das instâncias de aplicação, a concorrência, a idempotência e a replicação síncrona do PostgreSQL no Docker Compose local. Não apaga volumes nem dados. Executar na raiz do repositório, com o Docker Desktop ativo e o `.env` preenchido (ver `guia_execucao.md`).

> **Limite importante:** `auth1`/`auth2` e `booking1`/`booking2` são pares de instâncias equivalentes, sem primário e secundário. Só o PostgreSQL tem um primário (`postgres`) e uma réplica (`postgres-replica`). A réplica é síncrona, mas não há failover automático nem encaminhamento dos serviços para a réplica. **Não pares nem mates o primário PostgreSQL** à espera que a réplica assuma o serviço.

> Se o `.env` não estiver na raiz do repositório, acrescentar `--env-file <caminho>` a todos os comandos `docker compose`.

## 1. Preparação

Abrir três terminais na raiz do repositório.

No **Terminal 1**, arrancar tudo:

```bash
docker compose up -d --build
docker compose ps
```

Esperar que `postgres`, `postgres-replica`, `redis`, `auth1`, `auth2`, `booking1`, `booking2` e `mosquitto` estejam `healthy`. Os serviços `postgres-replication-role`, `postgres-enable-sync` e `auth-migrate` devem terminar com código 0 (`Exited (0)`); `nginx` e `web` não têm health check, por isso basta estarem `Up`.

No **Terminal 2**, abrir os logs:

```bash
docker compose logs -f --tail=50 nginx web auth1 auth2 booking1 booking2 postgres postgres-replica
```

Deixar este terminal aberto. `Ctrl+C` termina apenas a visualização dos logs, não os containers.

No **Terminal 3**, confirmar os endpoints através do Nginx e o estado síncrono:

```bash
curl -i http://127.0.0.1:8080/health/ready
curl -i http://127.0.0.1:8080/health/booking/ready
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
docker compose exec -T postgres-replica sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT pg_is_in_recovery();"'
```

Esperado: os dois health checks devolvem `200`; a réplica aparece como `studyspot_replica`, `streaming` e `sync`; `pg_is_in_recovery()` devolve `t`.

Abrir a interface em `https://localhost:8443` e aceitar o certificado local. Se ainda não houver uma conta de teste, selecionar **Criar conta**, preencher os dados, configurar o TOTP no Google Authenticator e confirmar o primeiro código; depois, iniciar sessão com a palavra-passe e o código TOTP. Para os cenários seguintes, usar uma conta já criada. A página **Estado** mostra se os serviços respondem.

## 2. D1 — Falha de uma instância de autenticação

```bash
docker compose stop auth1
curl -i http://127.0.0.1:8080/health/live
```

Na interface, terminar sessão e voltar a entrar (palavra-passe e código TOTP).

**Esperado:** o login funciona através de `auth2`. Nos logs, os pedidos seguintes chegam a `auth2`. Pode haver um atraso de cerca de 1 s no primeiro pedido, enquanto o Nginx deteta que `auth1` deixou de responder (deteção passiva).

Recuperar e esperar que fique `healthy`:

```bash
docker compose start auth1
docker compose ps auth1 auth2
```

## 3. D2 — Falha de uma instância de reservas

```bash
docker compose stop booking1
curl -i http://127.0.0.1:8080/health/booking/live
```

Na interface, criar uma reserva.

**Esperado:** a reserva é confirmada através de `booking2` e os logs mostram os pedidos a chegar a essa instância.

```bash
docker compose start booking1
docker compose ps booking1 booking2
```

## 4. D3 — Pedidos simultâneos para o mesmo slot

Abrir uma janela normal e uma janela anónima no browser, com duas contas diferentes. Em ambas, pedir a **mesma sala** para o **mesmo dia e horário** e carregar em "Reservar" quase ao mesmo tempo.

**Esperado:** um pedido é confirmado; o outro recebe "horário ocupado" e entra na lista de espera (ou recebe alternativas). Em "Salas", o slot aparece ocupado uma única vez. No pgAdmin, `SELECT sala_id, slot_inicio, count(*) FROM reserva_slots GROUP BY 1, 2 HAVING count(*) > 1;` não devolve linhas.

## 5. D4 — Réplica síncrona parada

Este teste **pára a réplica, não o primário**. Confirmar antes `sync_state = sync` (secção 1).

```bash
docker compose stop postgres-replica
```

Na interface, criar **uma** reserva de teste e cronometrar.

**Esperado:** a página fica à espera e, ao fim de cerca de 12 s, mostra que a reserva não foi confirmada. As leituras (Salas, As minhas reservas) continuam a funcionar. Não repetir o pedido.

Voltar a iniciar a réplica:

```bash
docker compose start postgres-replica
docker compose ps postgres postgres-replica
docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT application_name, state, sync_state FROM pg_stat_replication;"'
```

**Esperado:** o primário volta a mostrar `streaming` e `sync`, e a reserva pendente aparece em "As minhas reservas" **uma única vez**: a transação ficou à espera da réplica e concluiu quando ela voltou.

## 6. D5 — Reenvio do mesmo pedido

Na página "Reservar", submeter uma reserva. Voltar atrás no browser e submeter o **mesmo formulário** outra vez.

**Esperado:** é devolvida a mesma reserva, sem criar outra, porque o formulário reenvia a mesma `Idempotency-Key`.

## 7. Falha do primário PostgreSQL: o que não testar

**Não executar `docker compose stop postgres`, `docker stop` nem `docker kill` no primário como teste de failover.** Os serviços ligam-se ao hostname `postgres` e não existe Patroni, proxy de encaminhamento nem promoção automática. Se o primário parar, os pedidos que usam a base de dados falham e a réplica não passa a receber o tráfego. Não promover a réplica manualmente durante este guião.

A demonstração correta é: falha de uma instância de aplicação → a outra atende; falha da réplica → escritas ficam pendentes e nada se perde; falha do primário → indisponibilidade até recuperação manual (limite assumido).

## 8. Reposição e registo dos resultados

```bash
docker compose start auth1 booking1 postgres-replica
docker compose ps
```

Confirmar novamente os dois health checks da secção 1 e `sync_state = sync`. Para cada cenário, registar: o que continuou disponível, se houve erro inicial do Nginx, o tempo aproximado até a operação voltar a funcionar e a diferença entre falha de aplicação e falha da base de dados.

> Não executar `docker compose down -v`: a opção `-v` remove os volumes e apaga os dados.
