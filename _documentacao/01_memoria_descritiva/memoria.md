# Memória descritiva - StudySpot

## a) Identificação

- **Nome do projeto:** StudySpot - Sistema distribuído de reserva de salas de estudo com 2FA e check-in IoT.

- **Ano letivo:** 2026/2027

- **Semestre:** 5.º
- **Unidades curriculares:** 
* Projeto de Desenvolvimento de Software; 
* Engenharia de Software; 
* Segurança Informática; 
* Sistemas Distribuídos; 
* Inteligência Artificial.

- **Docentes:** 
* Rui Pascoal e Miguel Boavida (Projeto de Desenvolvimento de Software);
* Rui Ramos (Engenharia de Software); 
* Sérgio Nunes e Pedro Brandão (Segurança Informática); 
* Pedro Rosa (Sistemas Distribuídos); 
* Samuel Gomes (Inteligência Artificial).

- **Estado do documento:** atualizado na 2.ª entrega (15 de novembro de 2026).

## b) Resumo

O StudySpot é um sistema distribuído de reserva de salas de estudo para uma universidade, concebido no âmbito do Projeto de Desenvolvimento de Software da Licenciatura em Engenharia Informática (IADE – Universidade Europeia, 2026/2027, 5.º semestre). O projeto integra, numa única solução, conhecimentos de Engenharia de Software, Segurança Informática, Sistemas Distribuídos e Inteligência Artificial.

O problema abordado tem três vertentes: 
* **Primeiro:** as salas de estudo são um recurso escasso e os sistemas de reserva simples não impedem que dois pedidos simultâneos ocupem a mesma sala; 
* **Segundo:** a autenticação apenas por palavra-passe é vulnerável ao roubo e à adivinhação de credenciais;
* **Terceiro:** um sistema centralizado fica totalmente indisponível quando o seu servidor falha, o que é particularmente grave em períodos de exames. 

A estas vertentes junta-se a ocupação ineficiente: salas reservadas que ninguém utiliza.

A solução é uma aplicação web em que os estudantes se autenticam com palavra-passe e um segundo fator (código TOTP gerado, por exemplo, no Google Authenticator) e submetem pedidos de reserva. Cada pedido é validado automaticamente por um motor de Inteligência Artificial, um Problema de Satisfação de Restrições (CSP) desenvolvido pela equipa, que verifica a capacidade da sala, o horário de funcionamento, a ausência de sobreposição e o limite diário de 4 horas por estudante. Quando não há vaga, o pedido entra numa lista de espera e o estudante recebe os motivos e alternativas. À porta de cada sala, um leitor (ESP32 ou simulado) lê o QR Code da reserva e envia o check-in por MQTT; as reservas sem check-in dentro do prazo são libertadas e a sala é atribuída à lista de espera.

A arquitetura é distribuída e tolerante a faltas. Os serviços de autenticação e de reservas, desenvolvidos em Python com FastAPI, correm em duas instâncias sem estado cada, atrás de um Nginx que termina o HTTPS e balanceia os pedidos. Os dados persistem num PostgreSQL com um primário e uma réplica em replicação síncrona, e o Redis guarda as sessões, as tentativas de login e os locks distribuídos. A consistência das reservas combina um lock distribuído, uma restrição UNIQUE na base de dados e chaves de idempotência, de modo a impedir reservas duplicadas mesmo sob concorrência e perante falhas. Todos os componentes executam em containers Docker, geridos com Docker Compose.

Na 1.ª entrega foram feitas a análise e a conceptualização. Na 2.ª entrega foi apresentado um protótipo funcional do sistema distribuído: login com 2FA, reservas validadas pelo CSP, lista de espera, concorrência, redundância das instâncias e replicação síncrona, com 165 testes automatizados e cenários de falha demonstrados ao vivo. A 3.ª entrega iremos ativar o check-in por QR Code e MQTT e a realocação automática, e fecha a avaliação experimental.

## c) Contexto

### Problema abordado

- **Concorrência:** pedidos simultâneos para a mesma sala e horário podem originar reservas duplicadas;
- **Autenticação fraca:** a dependência exclusiva da palavra-passe expõe o sistema ao roubo e à adivinhação de credenciais;
- **Indisponibilidade:** um servidor centralizado deixa o serviço totalmente indisponível quando falha, sobretudo em época de exames;
- **Ocupação ineficiente:** salas reservadas que ninguém utiliza.

### Motivação

As salas de estudo de uma universidade são um recurso escasso e muito procurado. O problema é adequado para integrar, de forma coerente, as quatro áreas do semestre: engenharia de software, segurança informática, sistemas distribuídos e inteligência artificial, cumprindo o requisito do briefing de propor uma solução distribuída que resolva uma necessidade real.

### Objetivos

| # | Objetivo | Estado na 2.ª entrega |
|---|---|---|
| 1 | Autenticar com palavra-passe e segundo fator (TOTP) | Implementado |
| 2 | Arquitetura distribuída com redundância nas camadas de serviços e de dados | Implementado (2× auth, 2× booking, réplica síncrona); Nginx, Redis e cliente web continuam únicos |
| 3 | Impedir reservas duplicadas, mesmo sob concorrência e falhas | Implementado (lock Redis + UNIQUE + idempotência) |
| 4 | Validar e atribuir reservas com um CSP | Implementado (motor próprio, 66 testes) |
| 5 | Check-in IoT (MQTT) e libertação automática de reservas não utilizadas | Código e testes prontos, desligado por omissão (3.ª entrega) |
| 6 | Definir o modelo de faltas e demonstrá-lo com falhas provocadas | Implementado e demonstrado |
| 7 | Rastreabilidade das operações relevantes (auditoria) | Por implementar (3.ª entrega) |
| 8 | Metodologia ágil, com controlo de versões e artefactos auditáveis | Em curso |

## d) Processo

### Metodologia

Metodologia ágil e iterativa, com ciclos curtos alinhados com as três entregas (11/10, 15/11 e 20/12 de 2026). Cada ciclo percorre as fases do briefing: análise e conceptualização, planeamento, prototipagem, implementação, teste e apresentação. Na 2.ª entrega, o trabalho seguiu esta ordem: serviços isolados com testes, integração em Docker Compose, redundância das instâncias e replicação, e por fim os cenários de falha e a demonstração.

### Ferramentas

GitHub (branch `main` só com as versões entregues, branch `develop` para o trabalho diário), ClickUp (uma lista por área e uma lista de marcos com as datas das entregas), draw.io e Mermaid (diagramas) e pgAdmin (consulta da base de dados).

### Tecnologias

Python 3.12, FastAPI, Flask, SQLAlchemy, Alembic, PostgreSQL 18 (primário e réplica síncrona), Redis 7, Nginx, Eclipse Mosquitto (MQTT), argon2-cffi, PyOTP, cryptography (AES-GCM), segno, Docker, Docker Compose e pytest.

Face à 1.ª entrega, duas escolhas mudaram com a implementação:
- **Cliente web em Flask em vez de Streamlit:** o Streamlit guarda o estado de cada utilizador na memória do processo, o que dificulta pôr várias instâncias atrás de um balanceador. Com Flask, a sessão fica no Redis e o cliente web é stateless como os restantes serviços;
- **Motor CSP próprio em vez de `python-constraint`:** dá controlo sobre a explicação de cada recusa, a lista de espera, as alternativas e a estratégia de resolução (ver `04_documentacao_tecnica/componente_ia.md`).

### Estrutura da equipa

Equipa de quatro elementos, com uma área principal cada: segurança informática (serviço de autenticação), inteligência artificial e IoT (serviço de reservas, CSP e MQTT), sistemas distribuídos (infraestrutura, replicação e testes de falhas) e engenharia de software (interface, modelação e documentação). A integração e os testes de ponta a ponta são responsabilidade partilhada.

## e) Resultados

### Descrição da solução desenvolvida

Na 2.ª entrega, o StudySpot é um protótipo funcional executado com `docker compose up`. O estudante regista-se, configura o TOTP com um QR Code e inicia sessão em dois passos. Na página de reserva indica o número de pessoas, o dia e o horário; o motor CSP escolhe a sala mais pequena que serve, e a grelha de disponibilidade mostra a ocupação de todas as salas. Se não houver vaga, o pedido pode ficar em lista de espera até uma hora indicada. Em "As minhas reservas" o estudante vê o QR de check-in e pode cancelar.

Por baixo, o Nginx distribui os pedidos pelas instâncias `auth1`/`auth2` e `booking1`/`booking2` e deteta instâncias em falha. As sessões, as tentativas de login e os locks estão no Redis. Cada escrita só é confirmada depois de gravada no primário e na réplica do PostgreSQL. As capturas do protótipo estão em `02_imagens/img_09.png` a `img_14.png` e a arquitetura em `img_06.png`.

### Funcionalidades principais

- Registo e login em dois passos com TOTP (Google Authenticator);
- Reserva de salas com validação automática por CSP, recusa fundamentada, alternativas e lista de espera;
- Consulta da disponibilidade de todas as salas, por dia e em blocos de 30 minutos;
- Consulta e cancelamento das próprias reservas, QR Code de check-in e perfil com o resumo das reservas;
- Página de estado com os health checks dos serviços;
- Tolerância a faltas demonstrada com falhas provocadas (paragem de instâncias e da réplica);
- Check-in por QR Code e MQTT e libertação automática de reservas sem check-in (código pronto, desligado por omissão).

### Contributos relevantes

- Modelo de faltas com garantias e não-garantias explícitas, validado com falhas provocadas;
- Consistência das reservas assente na base de dados (restrição única por slot), com o lock distribuído como otimização e a idempotência para reenvios;
- Replicação síncrona que privilegia a durabilidade: uma reserva confirmada nunca existe só no primário;
- Motor CSP próprio, explicável, com duas estratégias (FIFO e maximizar) e análise de desempenho;
- 165 testes automatizados (135 reservas, 27 autenticação, 3 cliente web).

## f) Reflexão

### Lições aprendidas

- Definir primeiro as garantias que o sistema oferece e só depois escolher os mecanismos que as cumprem;
- Um lock distribuído reduz a contenção, mas só uma restrição na base de dados garante a correção;
- A replicação síncrona tem um custo real: com a réplica parada, as escritas ficam à espera. É uma escolha de consistência contra disponibilidade, e tem de ser explicada ao utilizador;
- O Nginx não repete um POST já enviado a uma instância que falhou; sem chave de idempotência, o reenvio do utilizador podia criar uma reserva duplicada;
- Ficheiros de configuração com fins de linha do Windows (CRLF) partem os scripts dos containers; os scripts em `database/postgres/` têm de ficar com fins de linha LF, o que um `.gitattributes` pode garantir;
- A coerência entre relatório, slides e modelo de faltas exige revisão cruzada entre as áreas.

### Limitações

Instâncias únicas de Nginx, Redis, cliente web e broker MQTT; promoção manual do primário do PostgreSQL; a réplica não serve leituras; sem token CSRF nos formulários; sem auditoria encadeada por hash; certificado HTTPS autoassinado; dispositivos IoT simulados; demonstração local.

### Trabalho futuro

Na 3.ª entrega: ativar o check-in por QR Code e MQTT e a realocação automática da lista de espera, introduzir redundância no Redis, automatizar ou documentar a promoção do PostgreSQL, adicionar uma segunda réplica para que a paragem de uma réplica não bloqueie as escritas, medir os tempos de recuperação de cada cenário, acrescentar a auditoria e finalizar a documentação.
