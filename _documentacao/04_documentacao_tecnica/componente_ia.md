# Componente de Inteligência Artificial — motor CSP

Código: `backend/booking_service/app/csp.py` (testes em `backend/booking_service/tests/test_csp.py`, 66 testes). Relatório da milestone: `Milestone2_IA_StudySpot.pdf`.

## 1. Porque um CSP

As regras das reservas são conhecidas, exatas e obrigatórias. Um Problema de Satisfação de Restrições garante por construção que nenhuma é violada, não precisa de dados históricos, é explicável (cada recusa tem um motivo e uma alternativa) e é extensível: uma regra nova é uma restrição nova, sem reescrever o algoritmo.

## 2. Modelo ⟨V, D, C⟩

| Elemento | No StudySpot |
|---|---|
| **Variáveis (V)** | Os pedidos. `PedidoReserva` tem horário fixo; `PedidoEspera` tem uma duração dentro de uma janela de tempo |
| **Domínios (D)** | Pares (sala, início). Num pedido fixo há um só início; num pedido em espera, todos os inícios de 30 em 30 minutos que cabem na janela |
| **Restrições (C)** | Capacidade da sala ≥ número de pessoas; reserva dentro do horário da sala; sem sobreposição na mesma sala; no máximo 4 h por estudante e por dia; horas alinhadas a blocos de 30 min, no mesmo dia, com pelo menos 1 pessoa |

Cada verificação (`verificar_capacidade`, `verificar_janela`, `verificar_sobreposicao`, `verificar_limite_diario`, `verificar_estrutura`, `verificar_ativa`) devolve `None` se a regra se cumpre, ou a mensagem com o motivo, o que permite explicar exatamente porque um pedido foi recusado.

## 3. Resolução

1. **Construção do domínio (`_dominio`):** as restrições unárias (sala ativa, capacidade, horário, estrutura) são aplicadas logo aqui, eliminando à partida as opções impossíveis. É a consistência de nó;
2. **Ordenação dos valores:** por hora de início e, depois, pela menor capacidade que serve, para não ocupar salas grandes com grupos pequenos;
3. **Atribuição:**
   - **`fifo`** (por omissão): pedidos por ordem de chegada; cada um recebe o primeiro valor compatível com as reservas existentes e as já atribuídas no lote. Justo, determinista e rápido;
   - **`maximizar`**: backtracking com poda (*branch and bound*) que maximiza o número de pedidos servidos. Um ramo é cortado quando os atribuídos mais os que faltam já não podem superar a melhor solução;
4. **Resultado (`Resolucao`):** atribuições, horários, motivos de rejeição e pedidos que podem ficar em lista de espera.

Um pedido que falha só por falta de vaga vai para a lista de espera (202); um pedido impossível (por exemplo, grupo maior do que todas as salas) é recusado (422). `sugerir_alternativas` propõe outras salas no mesmo horário e até três horários próximos no mesmo dia.

## 4. Desempenho

| Cenário | `fifo` | `maximizar` |
|---|---|---|
| 100 pedidos | ~3 ms | — |
| 1000 pedidos | ~150 ms | — |
| Escassez (3 salas, 14 pedidos) | serve 7,8 em média | serve 8,8, em ~100 ms |
| Salas de sobra (8 salas) | igual ao `maximizar` | 9 pedidos ~500 ms; 10 pedidos ~3 s |

O `fifo` avalia no máximo n·d combinações; o `maximizar` tem (d+1)ⁿ ramos no pior caso. Conclusão: o `fifo` é a estratégia do uso corrente; o `maximizar` serve de referência e para lotes pequenos em escassez. Os valores vêm do relatório da milestone de IA.

## 5. Integração no sistema

| Momento | Função | O que acontece |
|---|---|---|
| Novo pedido | `servico_reservas.criar_reserva` | Idempotência → CSP escolhe sala → locks Redis → INSERT. Se a restrição UNIQUE falhar porque outro pedido ganhou o slot, o CSP decide outra vez (até 3 vezes) |
| No-show «3.ª entrega» | `libertar_e_realocar` | Liberta reservas sem check-in 15 min após o início e chama `realocar_espera` |
| Realocação «3.ª entrega» | `realocar_espera` | Resolve toda a lista de espera de uma vez, por ordem de chegada, e grava com a chave `espera-<id>` |

O CSP decide o que é válido; a restrição UNIQUE da base de dados garante que não há duplicados. O motor comunica com o serviço através das interfaces `Repositorio` e `Locks`, o que permite testá-lo sem base de dados.

## 6. Alterações face à 1.ª entrega

Na 1.ª entrega estavam previstos a biblioteca `python-constraint`, forward checking, as heurísticas MRV e de grau e AC-3. Na implementação optou-se por um motor próprio com `fifo` e `maximizar`: cada pedido novo é resolvido isoladamente e a realocação trata lotes pequenos, pelo que a propagação de restrições traria pouco ganho. O AC-3 também não se aplica sem cuidado ao `maximizar`, porque um pedido pode legitimamente ficar por atribuir.

## 7. Próximos passos

- Expor a estratégia como parâmetro do serviço e usar o `maximizar` na realocação da lista de espera;
- Medir a ocupação efetiva das salas com e sem libertação automática.
