"""Testes do csp.py. Correr a partir de 05_artefactos/backend/booking_service:  python -m pytest -v"""

from datetime import datetime, time

import pytest

from app.csp import (ConfigCSP, MotorCSP, PedidoEspera, PedidoReserva, Reserva,
                     Sala, para_espera, resolver, slots_ocupados,
                     sugerir_alternativas, sugerir_sala_alternativa,
                     validar_capacidade, validar_horario, validar_limite_estudante,
                     validar_pedido, validar_reserva_csp)

DIA = (2026, 10, 20)


def dt(h: int, m: int = 0) -> datetime:
    return datetime(*DIA, h, m)


def sala(id="S1", cap=4, ab=time(8), fe=time(22), ativa=True) -> Sala:
    return Sala(id=id, capacidade=cap, abertura=ab, fecho=fe, ativa=ativa)


def pedido(id="P1", est="e1", n=2, ini=(10, 0), fim=(11, 0), criado=0, sala_id=None) -> PedidoReserva:
    return PedidoReserva(id=id, estudante_id=est, participantes=n,
                         inicio=dt(*ini), fim=dt(*fim),
                         criado_em=datetime(2026, 10, 19, 9, criado), sala_id=sala_id)


def reserva(id="R1", sala_id="S1", est="outro", ini=(10, 0), fim=(11, 0)) -> Reserva:
    return Reserva(id=id, sala_id=sala_id, estudante_id=est, inicio=dt(*ini), fim=dt(*fim))


# ---------------------- restrições individuais ----------------------

def test_pedido_valido():
    assert validar_pedido(pedido(), sala(), []).valido


def test_capacidade_excedida():
    r = validar_pedido(pedido(n=5), sala(cap=4), [])
    assert not r.valido and "comporta" in r.motivos[0]


def test_capacidade_exata_e_aceite():
    assert validar_pedido(pedido(n=4), sala(cap=4), []).valido


def test_antes_da_abertura():
    r = validar_pedido(pedido(ini=(7, 30), fim=(8, 30)), sala(ab=time(8)), [])
    assert not r.valido


def test_depois_do_fecho():
    r = validar_pedido(pedido(ini=(21, 30), fim=(22, 30)), sala(fe=time(22)), [])
    assert not r.valido


def test_termina_exatamente_ao_fecho_e_aceite():
    assert validar_pedido(pedido(ini=(21, 0), fim=(22, 0)), sala(fe=time(22)), []).valido


def test_horario_nao_alinhado_ao_bloco():
    r = validar_pedido(pedido(ini=(10, 15), fim=(11, 0)), sala(), [])
    assert not r.valido and "blocos" in r.motivos[0]


def test_fim_antes_do_inicio():
    assert not validar_pedido(pedido(ini=(11, 0), fim=(10, 0)), sala(), []).valido


def test_sobreposicao_parcial():
    r = validar_pedido(pedido(ini=(10, 30), fim=(11, 30)), sala(), [reserva()])
    assert not r.valido and "já está reservada" in r.motivos[0]


def test_reservas_encostadas_nao_colidem():
    assert validar_pedido(pedido(ini=(11, 0), fim=(12, 0)), sala(), [reserva()]).valido


def test_sobreposicao_noutra_sala_nao_conta():
    assert validar_pedido(pedido(), sala("S1"), [reserva(sala_id="S2")]).valido


def test_limite_diario_excedido():
    existentes = [reserva(est="e1", ini=(8, 0), fim=(11, 0))]  # 3h
    r = validar_pedido(pedido(est="e1", ini=(14, 0), fim=(15, 30)), sala(), existentes)  # +1.5h
    assert not r.valido and "Limite diário" in r.motivos[0]


def test_limite_diario_exato_e_aceite():
    existentes = [reserva(est="e1", ini=(8, 0), fim=(11, 0))]  # 3h
    assert validar_pedido(pedido(est="e1", ini=(14, 0), fim=(15, 0)), sala(), existentes).valido


def test_limite_diario_nao_conta_outros_dias_nem_estudantes():
    ontem = Reserva("R0", "S1", "e1", datetime(2026, 10, 19, 8), datetime(2026, 10, 19, 12))
    outro = reserva(est="e2", ini=(8, 0), fim=(12, 0))
    assert validar_pedido(pedido(est="e1", ini=(14, 0), fim=(16, 0)), sala(), [ontem, outro]).valido


def test_todos_os_motivos_sao_reportados():
    r = validar_pedido(pedido(n=9, ini=(6, 0), fim=(7, 0)), sala(), [])
    assert len(r.motivos) == 2  # capacidade + janela


# ---------------------- solver ----------------------

def test_fifo_o_mais_antigo_fica_com_a_sala():
    res = resolver([pedido("P2", est="e2", criado=5), pedido("P1", est="e1", criado=1)],
                   [sala("S1")])
    assert res.atribuicoes == {"P1": "S1"}
    assert "P2" in res.rejeitados


def test_segundo_pedido_vai_para_outra_sala():
    res = resolver([pedido("P1", criado=1), pedido("P2", est="e2", criado=2)],
                   [sala("S1"), sala("S2")])
    assert set(res.atribuicoes.values()) == {"S1", "S2"}


def test_prefere_a_sala_mais_pequena_que_sirva():
    res = resolver([pedido(n=2)], [sala("GRANDE", cap=10), sala("PEQUENA", cap=2)])
    assert res.atribuicoes == {"P1": "PEQUENA"}


def test_sala_preferida_e_respeitada():
    res = resolver([pedido(sala_id="S2")], [sala("S1"), sala("S2")])
    assert res.atribuicoes == {"P1": "S2"}


def test_pedido_impossivel_fica_rejeitado_com_motivo():
    res = resolver([pedido(n=50)], [sala()])
    assert res.atribuicoes == {} and "comporta" in res.rejeitados["P1"][0]


def test_respeita_reservas_existentes():
    res = resolver([pedido()], [sala("S1")], [reserva()])
    assert res.atribuicoes == {} and "P1" in res.rejeitados


def test_limite_diario_aplica_se_entre_pedidos_do_mesmo_lote():
    p1 = pedido("P1", est="e1", ini=(8, 0), fim=(11, 0), criado=1)   # 3h
    p2 = pedido("P2", est="e1", ini=(13, 0), fim=(15, 0), criado=2)  # +2h = 5h > 4h
    res = resolver([p1, p2], [sala()])
    assert list(res.atribuicoes) == ["P1"]
    assert "Limite diário" in res.rejeitados["P2"][0]


def _cenario_fifo_vs_maximizar():
    p1 = pedido("P1", est="e1", ini=(8, 0), fim=(11, 0), criado=1)   # 3h
    p2 = pedido("P2", est="e1", ini=(12, 0), fim=(14, 0), criado=2)  # 2h
    p3 = pedido("P3", est="e1", ini=(15, 0), fim=(17, 0), criado=3)  # 2h
    return [p1, p2, p3], [sala()]


def test_fifo_prioriza_o_mais_antigo():
    pedidos, salas = _cenario_fifo_vs_maximizar()
    res = resolver(pedidos, salas, cfg=ConfigCSP(estrategia="fifo"))
    assert set(res.atribuicoes) == {"P1"}


def test_maximizar_serve_mais_pedidos_com_backtracking():
    pedidos, salas = _cenario_fifo_vs_maximizar()
    res = resolver(pedidos, salas, cfg=ConfigCSP(estrategia="maximizar"))
    assert set(res.atribuicoes) == {"P2", "P3"}


def test_maximizar_desempata_a_favor_do_mais_antigo():
    res = resolver([pedido("P1", criado=1), pedido("P2", est="e2", criado=2)],
                   [sala("S1")], cfg=ConfigCSP(estrategia="maximizar"))
    assert set(res.atribuicoes) == {"P1"}


def test_estrategia_invalida():
    with pytest.raises(ValueError):
        resolver([pedido()], [sala()], cfg=ConfigCSP(estrategia="xpto"))


def test_lista_vazia():
    assert resolver([], [sala()]).atribuicoes == {}


# ---------------------- alinhamento com os diagramas ----------------------

def test_sala_inativa_e_rejeitada():
    r = validar_pedido(pedido(), sala(ativa=False), [])
    assert not r.valido and "não está disponível" in r.motivos[0]
    assert resolver([pedido()], [sala(ativa=False)]).atribuicoes == {}


def test_sem_vaga_vai_para_lista_de_espera_por_ordem_fifo():
    res = resolver([pedido("P1", criado=1), pedido("P2", est="e2", criado=2),
                    pedido("P3", est="e3", criado=3)], [sala("S1")])
    assert res.atribuicoes == {"P1": "S1"}
    assert res.lista_espera == ["P2", "P3"]


def test_pedido_impossivel_nao_vai_para_lista_de_espera():
    res = resolver([pedido(n=50)], [sala()])
    assert "P1" in res.rejeitados and res.lista_espera == []


def test_limite_diario_nao_vai_para_lista_de_espera():
    p1 = pedido("P1", est="e1", ini=(8, 0), fim=(11, 0), criado=1)
    p2 = pedido("P2", est="e1", ini=(13, 0), fim=(15, 0), criado=2)
    res = resolver([p1, p2], [sala()])
    assert "P2" in res.rejeitados and res.lista_espera == []


def test_reexecucao_apos_libertar_reserva_realoca_a_lista_de_espera():
    espera = [pedido("P2", est="e2", criado=2), pedido("P3", est="e3", criado=3)]
    antes = resolver(espera, [sala()], [reserva()])               # sala ocupada
    assert antes.atribuicoes == {} and antes.lista_espera == ["P2", "P3"]
    depois = resolver(espera, [sala()], [])                       # reserva libertada
    assert depois.atribuicoes == {"P2": "S1"} and depois.lista_espera == ["P3"]


def test_slots_ocupados():
    assert slots_ocupados(dt(10), dt(11, 30)) == [dt(10), dt(10, 30), dt(11)]


def test_alternativas_outras_salas_no_mesmo_horario():
    alt = sugerir_alternativas(pedido(sala_id="S1"), [sala("S1"), sala("S2")], [reserva()])
    assert alt.salas == ["S2"]


def test_alternativas_horarios_proximos_na_mesma_sala():
    alt = sugerir_alternativas(pedido(), [sala("S1")], [reserva()])  # S1 ocupada 10-11
    assert alt.salas == []
    assert alt.horarios[:2] == [("S1", dt(9), dt(10)), ("S1", dt(11), dt(12))]


def test_alternativas_pedido_mal_formado_devolve_vazio():
    alt = sugerir_alternativas(pedido(ini=(11, 0), fim=(10, 0)), [sala()], [])
    assert alt.salas == [] and alt.horarios == []


def test_motor_csp_fachada_equivale_as_funcoes():
    pedidos = [pedido("P1", criado=1), pedido("P2", est="e2", criado=2)]
    motor = MotorCSP(ConfigCSP())
    assert motor.resolver(pedidos, [sala()], []).atribuicoes == resolver(pedidos, [sala()]).atribuicoes
    assert motor.validar(pedido(), sala(), []).valido


# ---------------------- lista de espera com janela + duração ----------------------

def espera(id="W1", est="e1", n=2, ini=(10, 0), fim=(13, 0), dur=60, criado=0,
           sala_id=None) -> PedidoEspera:
    return PedidoEspera(id=id, estudante_id=est, participantes=n,
                        janela_inicio=dt(*ini), janela_fim=dt(*fim), duracao_minutos=dur,
                        criado_em=datetime(2026, 10, 19, 9, criado), sala_id=sala_id)


def test_espera_escolhe_a_primeira_hora_livre_na_janela():
    res = resolver([espera()], [sala("S1")], [reserva(ini=(10, 0), fim=(11, 0))])
    assert res.atribuicoes == {"W1": "S1"}
    assert res.horarios["W1"] == (dt(11), dt(12))


def test_espera_ocupa_a_hora_mais_cedo_quando_tudo_livre():
    res = resolver([espera()], [sala("S1")], [])
    assert res.horarios["W1"] == (dt(10), dt(11))


def test_espera_sem_hora_livre_continua_em_lista_de_espera():
    res = resolver([espera()], [sala("S1")], [reserva(ini=(10, 0), fim=(13, 0))])
    assert res.atribuicoes == {} and res.lista_espera == ["W1"]
    assert "Não há horário livre" in res.rejeitados["W1"][0]


def test_espera_duracao_maior_que_a_janela_e_rejeitada_de_vez():
    res = resolver([espera(dur=240)], [sala()])  # janela de 3h, pede 4h
    assert res.lista_espera == [] and "não cabe" in res.rejeitados["W1"][0]


def test_espera_respeita_o_horario_de_funcionamento_da_sala():
    res = resolver([espera(ini=(6, 0), fim=(9, 0))], [sala(ab=time(8))])
    assert res.horarios["W1"] == (dt(8), dt(9))


def test_espera_respeita_o_limite_diario():
    existentes = [reserva(est="e1", ini=(8, 0), fim=(11, 30))]  # 3.5h
    res = resolver([espera(est="e1", ini=(14, 0), fim=(16, 0))], [sala()], existentes)
    assert res.atribuicoes == {} and res.lista_espera == []
    assert "Limite diário" in res.rejeitados["W1"][0]


def test_dois_pedidos_flexiveis_dividem_a_janela():
    res = resolver([espera("W1", est="e1", criado=1, fim=(12, 0)),
                    espera("W2", est="e2", criado=2, fim=(12, 0))], [sala()])
    assert res.horarios["W1"] == (dt(10), dt(11))
    assert res.horarios["W2"] == (dt(11), dt(12))


def test_pedido_fixo_e_flexivel_no_mesmo_lote():
    fixo = pedido("P1", est="e1", ini=(10, 0), fim=(11, 0), criado=1)
    res = resolver([fixo, espera("W1", est="e2", criado=2, fim=(12, 0))], [sala()])
    assert res.horarios["P1"] == (dt(10), dt(11))
    assert res.horarios["W1"] == (dt(11), dt(12))


def test_flexivel_com_maximizar_tambem_funciona():
    res = resolver([espera("W1", est="e1", criado=1, fim=(12, 0)),
                    espera("W2", est="e2", criado=2, fim=(12, 0))], [sala()],
                   cfg=ConfigCSP(estrategia="maximizar"))
    assert set(res.atribuicoes) == {"W1", "W2"}


def test_para_espera_converte_pedido_recusado():
    e = para_espera(pedido("P9", ini=(10, 0), fim=(11, 30)))
    assert (e.janela_inicio, e.janela_fim, e.duracao_minutos) == (dt(10), dt(11, 30), 90)


def test_recusado_e_reavaliado_como_espera_apos_libertar_a_sala():
    recusado = pedido("P9", est="e9", ini=(10, 0), fim=(11, 0))
    res1 = resolver([recusado], [sala()], [reserva()])               # sala ocupada
    assert res1.lista_espera == ["P9"]
    res2 = resolver([para_espera(recusado)], [sala()], [])           # reserva libertada
    assert res2.horarios["P9"] == (dt(10), dt(11))


# ---------------------- API simples do enunciado ----------------------

ABRE, FECHA = time(8, 0), time(22, 0)
SALAS = {"A1": 4, "B2": 8, "C3": 12}


def req(est="e1", sala="A1", n=3, ini=(10, 0), fim=(11, 0)):
    return {"estudante_id": est, "sala_id": sala, "num_pessoas": n,
            "inicio": dt(*ini), "fim": dt(*fim)}


def test_validar_capacidade_primitiva():
    assert validar_capacidade(4, 4) and validar_capacidade(1, 4)
    assert not validar_capacidade(5, 4)


def test_validar_horario_primitiva():
    assert validar_horario(time(10), time(11), ABRE, FECHA)
    assert validar_horario(time(8), time(22), ABRE, FECHA)       # extremos permitidos
    assert not validar_horario(time(7, 30), time(9), ABRE, FECHA)
    assert not validar_horario(time(21), time(22, 30), ABRE, FECHA)
    assert not validar_horario(time(11), time(10), ABRE, FECHA)  # fim antes do início
    assert not validar_horario(time(10), time(10), ABRE, FECHA)  # duração zero


def test_validar_limite_estudante_primitiva():
    assert validar_limite_estudante("e1", 4.0, {})
    assert validar_limite_estudante("e1", 1.0, {"e1": 3.0})      # exatamente 4h
    assert not validar_limite_estudante("e1", 1.5, {"e1": 3.0})
    assert validar_limite_estudante("e1", 4.0, {"outro": 4.0})   # outros estudantes não contam
    assert not validar_limite_estudante("e1", 3.0, {"e1": 1.0}, limite_diario=3.0)


def test_limite_estudante_tolera_erros_de_virgula_flutuante():
    assert validar_limite_estudante("e1", 0.3, {"e1": 3.7})      # 3.7 + 0.3 = 4.000000000000001


def test_reserva_valida_devolve_mensagem_com_os_dados():
    ok, msg = validar_reserva_csp(req(), SALAS, ABRE, FECHA, {})
    assert ok and "A1" in msg and "10:00-11:00" in msg


def test_reserva_falha_por_lotacao():
    ok, msg = validar_reserva_csp(req(n=6), SALAS, ABRE, FECHA, {})
    assert not ok and "comporta 4" in msg


def test_reserva_falha_por_horario_fora_do_funcionamento():
    ok, msg = validar_reserva_csp(req(ini=(7, 0), fim=(8, 30)), SALAS, ABRE, FECHA, {})
    assert not ok and "fora do funcionamento" in msg


def test_reserva_falha_por_fim_antes_do_inicio():
    ok, msg = validar_reserva_csp(req(ini=(11, 0), fim=(10, 0)), SALAS, ABRE, FECHA, {})
    assert not ok and "posterior" in msg


def test_reserva_falha_por_limite_do_estudante():
    ok, msg = validar_reserva_csp(req(est="e1", sala="B2", ini=(14, 0), fim=(15, 30)),
                                  SALAS, ABRE, FECHA, {"e1": 3.0})
    assert not ok and "limite diário" in msg


def test_reserva_que_atravessa_a_meia_noite_e_rejeitada():
    r = req()
    r["fim"] = datetime(2026, 10, 21, 1, 0)
    ok, msg = validar_reserva_csp(r, SALAS, ABRE, FECHA, {})
    assert not ok and "mesmo dia" in msg


def test_reserva_com_sala_inexistente_ou_campos_em_falta():
    assert not validar_reserva_csp(req(sala="Z9"), SALAS, ABRE, FECHA, {})[0]
    incompleto = req()
    del incompleto["fim"]
    ok, msg = validar_reserva_csp(incompleto, SALAS, ABRE, FECHA, {})
    assert not ok and "fim" in msg
    assert not validar_reserva_csp(req(n=0), SALAS, ABRE, FECHA, {})[0]


def test_a_primeira_violacao_e_a_reportada():
    # lotação E horário violados: a ordem (capacidade, horário, limite) decide
    ok, msg = validar_reserva_csp(req(n=9, ini=(6, 0), fim=(7, 0)), SALAS, ABRE, FECHA, {})
    assert not ok and "comporta" in msg


def test_alternativa_escolhe_a_menor_sala_que_serve():
    assert sugerir_sala_alternativa(req(n=6), SALAS, ABRE, FECHA, {}) == "B2"
    assert sugerir_sala_alternativa(req(n=10), SALAS, ABRE, FECHA, {}) == "C3"


def test_alternativa_ignora_salas_ocupadas_nesse_horario():
    ocupadas = [{"sala_id": "B2", "inicio": dt(10, 30), "fim": dt(11, 30)}]
    assert sugerir_sala_alternativa(req(n=6), SALAS, ABRE, FECHA, {},
                                    reservas_existentes=ocupadas) == "C3"


def test_alternativa_reserva_encostada_nao_bloqueia_a_sala():
    encostada = [{"sala_id": "B2", "inicio": dt(9), "fim": dt(10)}]
    assert sugerir_sala_alternativa(req(n=6), SALAS, ABRE, FECHA, {},
                                    reservas_existentes=encostada) == "B2"


def test_alternativa_so_ajuda_quando_falha_por_lotacao():
    # cabe na sala pedida mas está fora de horas: outra sala não resolve
    assert sugerir_sala_alternativa(req(n=2, ini=(7, 0), fim=(8, 0)), SALAS, ABRE, FECHA, {}) is None


def test_alternativa_inexistente_devolve_none():
    assert sugerir_sala_alternativa(req(n=50), SALAS, ABRE, FECHA, {}) is None


def test_alternativa_respeita_o_limite_do_estudante():
    # mesmo havendo sala maior livre, o limite diário impede qualquer sala
    assert sugerir_sala_alternativa(req(est="e1", n=6, ini=(14, 0), fim=(16, 0)),
                                    SALAS, ABRE, FECHA, {"e1": 3.0}) is None
