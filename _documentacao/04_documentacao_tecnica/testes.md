# Testes — StudySpot

Há dois níveis de verificação:

1. **Testes automatizados (pytest):** verificam a lógica de cada componente sem Docker, com SQLite em memória e um Redis simulado;
2. **Cenários de falha:** executados com a composição completa em funcionamento, parando containers (ver `guiao_teste_tolerancia_falhas.md` e `modelo_de_faltas.md`, secção 12).

## 1. Testes automatizados

Como correr: ver `guia_execucao.md`, secção 7. Na 2.ª entrega a suite tem **165 testes**.

| Componente | Ficheiros principais | Testes |
|---|---|---|
| Reservas (`backend/booking_service/tests/`) | `test_csp.py` (66), `test_servico_reservas.py` (16), `test_bookings.py` (13), `test_repo_sql.py` (11), `test_checkin_mqtt.py` (8), `test_fluxo_sql.py` (6), `test_health.py` (4), `test_locks_redis.py` (4), `test_sessoes_auth.py` (4), `test_qr_checkin.py` (3) | 135 |
| Autenticação (`backend/auth_service/tests/`) | `test_auth.py`, `test_auth_flow.py`, `test_routes_auth.py`, `test_health.py`, `test_models.py`, `test_schemas.py` | 27 |
| Cliente web (`frontend/web_client/tests/`) | `test_auth_routes.py` | 3 |
| **Total** | | **165** |

Os 11 testes de check-in MQTT e QR Code cobrem código já escrito, cuja integração está desligada por omissão até à 3.ª entrega.

## 2. Rastreabilidade entre requisitos e testes

| Requisito | Verificado por |
|---|---|
| Registo e login com TOTP | `test_registo_confirma_totp_e_login_emite_sessao`, `test_registo_e_confirmacao_totp_usam_auth_service` |
| Regras da reserva (capacidade, horário, sobreposição, limite diário) | `test_csp.py` |
| Sem duas reservas para o mesmo slot | `test_base_de_dados_recusa_slot_duplicado_mesmo_sem_o_servico`, `test_corrida_conflito_de_slot_e_decidido_de_novo_noutra_sala`, cenário D3 |
| Idempotência | `test_idempotencia_reenvio_nao_duplica`, `test_chave_repetida_devolve_a_reserva_existente`, cenário D5 |
| Lista de espera e alternativas | `test_sala_ocupada_vai_para_espera_com_alternativas`, `test_pedido_impossivel_e_recusado_e_nao_entra_em_espera` |
| Cancelar e sair da lista de espera | `test_cancelar_e_idempotente_e_so_pelo_dono`, `test_esperas_do_utilizador_e_sair` |
| Logout revoga a sessão | `test_login_totp_guarda_token_central_e_logout_revoga` |
| Argon2 e AES-GCM | `test_hash_e_verificacao_de_palavra_passe`, `test_cifra_e_decifra_segredo_totp`, `test_rejeita_chave_incorreta_ao_decifrar_totp` |
| Limitação de tentativas e anti-reutilização do TOTP | `test_login_tem_mensagem_generica_e_limita_tentativas`, `test_totp_reutilizado_nao_emite_outra_sessao` |
| Health checks | `test_ready_devolve_503_se_postgres_falhar`, `test_ready_devolve_503_se_redis_falhar` |
| Falha segura sem Redis | `test_lock_indisponivel_falha_segura_sem_gravar`, `test_falha_redis_devolve_503` |
| Expiração das sessões | `test_sessao_expirada_devolve_401`, `test_sessao_bearer_valida_e_renova_inatividade` |
| Continuidade com uma instância em baixo | cenários D1 e D2 |
| Escritas só confirmadas com a réplica | cenário D4 |
| Libertação e realocação «3.ª entrega» | `test_liberta_fantasma_e_realoca_a_lista_de_espera`, `test_broker_em_baixo_nao_liberta_nada`, `test_tarefa_repetida_e_idempotente` |

## 3. Cenários de falha (2.ª entrega)

| ID | Cenário | Comportamento esperado |
|---|---|---|
| D1 | Parar `auth1` e iniciar sessão | Login funciona através de `auth2` |
| D2 | Parar `booking1` e criar reserva | Reserva criada através de `booking2` |
| D3 | Dois pedidos simultâneos para a mesma sala e slot | Um confirmado (201), o outro em espera (202) |
| D4 | Parar a réplica e criar reserva; voltar a iniciar a réplica | Erro após ~12 s; a reserva aparece depois de a réplica voltar, sem duplicados |
| D5 | Repetir o mesmo formulário de reserva | Mesma reserva devolvida (200), sem duplicação |

Os resultados e medições dos cenários (tempos de deteção e de recuperação) devem ser guardados em `06_dados_investigacao/`.
