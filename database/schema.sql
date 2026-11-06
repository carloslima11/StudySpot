--
-- PostgreSQL database dump
--

\restrict aIAgc82xM7BkRZXX0LUjgPQegiNnMhtguiIeaNnWI2To6grTz1tAtaavamOpgUL

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

-- Started on 2026-11-06 11:28:03

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 223 (class 1259 OID 16420)
-- Name: codigos_recuperacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.codigos_recuperacao (
    c_id integer NOT NULL,
    c_utilizador_id integer,
    hash character varying(100),
    usado_em timestamp(6) with time zone
);


--
-- TOC entry 224 (class 1259 OID 16431)
-- Name: credenciais_presenca; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.credenciais_presenca (
    cp_id integer NOT NULL,
    cp_utilizador_id integer,
    tipo character varying(100),
    valor_hmac character varying(100)
);


--
-- TOC entry 227 (class 1259 OID 16510)
-- Name: dispositivos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.dispositivos (
    dispositivos_id integer NOT NULL,
    d_sala_id integer,
    ativo boolean
);


--
-- TOC entry 221 (class 1259 OID 16399)
-- Name: eventos_auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eventos_auditoria (
    eventos_id integer NOT NULL,
    quando timestamp(6) with time zone,
    ator_tipo character varying(100),
    ator_id integer,
    tipo character varying(100),
    detalhe json,
    hash_anterior character varying(100),
    hash character varying(100)
);


--
-- TOC entry 225 (class 1259 OID 16444)
-- Name: lista_espera; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lista_espera (
    lista_id integer NOT NULL,
    lista_utilizador_id integer NOT NULL,
    n_pessoas integer NOT NULL,
    janela_inicio timestamp(6) with time zone,
    janela_fim timestamp(6) with time zone,
    duracao integer,
    criado_em timestamp(6) with time zone,
    estago character varying
);


--
-- TOC entry 228 (class 1259 OID 16527)
-- Name: reserva_slots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reserva_slots (
    reserva_id integer,
    reserva_sala_id integer,
    slot_inicio timestamp(6) with time zone
);


--
-- TOC entry 226 (class 1259 OID 16457)
-- Name: reservas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.reservas (
    reservas_id integer NOT NULL,
    reservas__utilizador_id integer NOT NULL,
    rsala_id integer,
    inicio timestamp(6) with time zone,
    fim timestamp(6) with time zone,
    r_n_pessoas integer,
    estado character varying(100),
    chave_idempotencia character varying(100),
    check_in_em timestamp(6) with time zone,
    criado_em date
);


--
-- TOC entry 220 (class 1259 OID 16393)
-- Name: salas; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.salas (
    salas_id integer NOT NULL,
    sala_nome character varying(100) NOT NULL,
    capacidade integer,
    abertura timestamp(6) with time zone,
    fecho timestamp(6) with time zone,
    ativa boolean
);


--
-- TOC entry 222 (class 1259 OID 16407)
-- Name: segredos_totp; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.segredos_totp (
    s_utilizador_id integer NOT NULL,
    segredo_cifrado bytea,
    nonce bytea,
    confirmado boolean,
    criado_em timestamp(6) with time zone
);


--
-- TOC entry 219 (class 1259 OID 16385)
-- Name: utilizadores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.utilizadores (
    utilizador_id integer NOT NULL,
    nome character varying(100) NOT NULL,
    email character varying(100) NOT NULL,
    palavra_passe_hash character varying(100) NOT NULL,
    ultimo_passo_totp bigint,
    ativo boolean,
    criado_em date
);


--
-- TOC entry 4902 (class 2606 OID 16425)
-- Name: codigos_recuperacao codigos_recuperacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.codigos_recuperacao
    ADD CONSTRAINT codigos_recuperacao_pkey PRIMARY KEY (c_id);


--
-- TOC entry 4904 (class 2606 OID 16436)
-- Name: credenciais_presenca credenciais_presenca_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credenciais_presenca
    ADD CONSTRAINT credenciais_presenca_pkey PRIMARY KEY (cp_id);


--
-- TOC entry 4912 (class 2606 OID 16515)
-- Name: dispositivos dispositivos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispositivos
    ADD CONSTRAINT dispositivos_pkey PRIMARY KEY (dispositivos_id);


--
-- TOC entry 4892 (class 2606 OID 16392)
-- Name: utilizadores email; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.utilizadores
    ADD CONSTRAINT email UNIQUE (email);


--
-- TOC entry 4898 (class 2606 OID 16406)
-- Name: eventos_auditoria eventos_auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eventos_auditoria
    ADD CONSTRAINT eventos_auditoria_pkey PRIMARY KEY (eventos_id);


--
-- TOC entry 4908 (class 2606 OID 16451)
-- Name: lista_espera lista_espera_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lista_espera
    ADD CONSTRAINT lista_espera_pkey PRIMARY KEY (lista_id);


--
-- TOC entry 4910 (class 2606 OID 16535)
-- Name: reservas reservas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT reservas_pkey PRIMARY KEY (reservas_id);


--
-- TOC entry 4896 (class 2606 OID 16398)
-- Name: salas salas_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.salas
    ADD CONSTRAINT salas_pkey PRIMARY KEY (salas_id);


--
-- TOC entry 4900 (class 2606 OID 16414)
-- Name: segredos_totp segredos_totp_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segredos_totp
    ADD CONSTRAINT segredos_totp_pkey PRIMARY KEY (s_utilizador_id);


--
-- TOC entry 4914 (class 2606 OID 16533)
-- Name: reserva_slots uq_reserva_slots; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva_slots
    ADD CONSTRAINT uq_reserva_slots UNIQUE (slot_inicio, reserva_sala_id);


--
-- TOC entry 4894 (class 2606 OID 16390)
-- Name: utilizadores utilizadores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.utilizadores
    ADD CONSTRAINT utilizadores_pkey PRIMARY KEY (utilizador_id);


--
-- TOC entry 4906 (class 2606 OID 16438)
-- Name: credenciais_presenca valor_hmac; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credenciais_presenca
    ADD CONSTRAINT valor_hmac UNIQUE (valor_hmac);


--
-- TOC entry 4916 (class 2606 OID 16426)
-- Name: codigos_recuperacao c_utilizador_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.codigos_recuperacao
    ADD CONSTRAINT c_utilizador_id FOREIGN KEY (c_utilizador_id) REFERENCES public.utilizadores(utilizador_id);


--
-- TOC entry 4917 (class 2606 OID 16439)
-- Name: credenciais_presenca cp_utilizador_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.credenciais_presenca
    ADD CONSTRAINT cp_utilizador_id FOREIGN KEY (cp_utilizador_id) REFERENCES public.utilizadores(utilizador_id);


--
-- TOC entry 4921 (class 2606 OID 16516)
-- Name: dispositivos d_sala_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.dispositivos
    ADD CONSTRAINT d_sala_id FOREIGN KEY (d_sala_id) REFERENCES public.salas(salas_id);


--
-- TOC entry 4922 (class 2606 OID 16538)
-- Name: reserva_slots fk_reservas_slots; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reserva_slots
    ADD CONSTRAINT fk_reservas_slots FOREIGN KEY (reserva_id) REFERENCES public.reservas(reservas_id) NOT VALID;


--
-- TOC entry 4918 (class 2606 OID 16452)
-- Name: lista_espera lista_utilizador_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lista_espera
    ADD CONSTRAINT lista_utilizador_id FOREIGN KEY (lista_utilizador_id) REFERENCES public.utilizadores(utilizador_id);


--
-- TOC entry 4919 (class 2606 OID 16464)
-- Name: reservas reservas_utilizador_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT reservas_utilizador_id FOREIGN KEY (reservas__utilizador_id) REFERENCES public.utilizadores(utilizador_id);


--
-- TOC entry 4920 (class 2606 OID 16469)
-- Name: reservas rsala_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.reservas
    ADD CONSTRAINT rsala_id FOREIGN KEY (rsala_id) REFERENCES public.salas(salas_id);


--
-- TOC entry 4915 (class 2606 OID 16415)
-- Name: segredos_totp s_utilizador_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.segredos_totp
    ADD CONSTRAINT s_utilizador_id FOREIGN KEY (s_utilizador_id) REFERENCES public.utilizadores(utilizador_id);


-- Completed on 2026-11-06 11:28:03

--
-- PostgreSQL database dump complete
--

\unrestrict aIAgc82xM7BkRZXX0LUjgPQegiNnMhtguiIeaNnWI2To6grTz1tAtaavamOpgUL

