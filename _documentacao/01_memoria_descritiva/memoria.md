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

## b) Resumo

O StudySpot é um sistema distribuído de reserva de salas de estudo para uma universidade, concebido no âmbito do Projeto de Desenvolvimento de Software da Licenciatura em Engenharia Informática (IADE – Universidade Europeia, 2026/2027, 5.º semestre). O projeto integra, numa única solução, conhecimentos de Engenharia de Software, Segurança Informática, Sistemas Distribuídos e Inteligência Artificial.

O problema abordado tem três vertentes: 
* **Primeiro:** as salas de estudo são um recurso escasso e os sistemas de reserva simples não impedem que dois pedidos simultâneos ocupem a mesma sala; 
* **Segundo:** a autenticação apenas por palavra-passe é vulnerável ao roubo e à adivinhação de credenciais;
* **Terceiro:** um sistema centralizado fica totalmente indisponível quando o seu servidor falha, o que é particularmente grave em períodos de exames. 

A estas vertentes junta-se a ocupação ineficiente: salas reservadas que ninguém utiliza.

A solução proposta é uma aplicação web em que os estudantes se autenticam com palavra-passe e um segundo fator (código TOTP gerado, por exemplo, no Google Authenticator) e submetem pedidos de reserva. Cada pedido é validado automaticamente por um algoritmo de Inteligência Artificial, o Problema de Satisfação de Restrições (CSP), que verifica a capacidade da sala, o horário de funcionamento e os limites de utilização por estudante. À porta de cada sala, um dispositivo IoT (ESP32 com leitor RFID ou QR code, real ou simulado) regista o check-in e envia o evento por MQTT. As reservas sem check-in dentro do prazo são libertadas e a sala é atribuída a pedidos em lista de espera.

A arquitetura é distribuída e tolerante a faltas. Os serviços de autenticação e de reservas, desenvolvidos em Python com FastAPI, correm em duas ou mais instâncias sem estado, atrás de um balanceador de carga Nginx. Os dados persistem numa base de dados PostgreSQL com replicação entre um servidor primário e uma réplica, e o Redis assegura sessões partilhadas e locks distribuídos. A consistência das reservas combina um lock distribuído, uma restrição UNIQUE na base de dados e chaves de idempotência, de modo a impedir reservas duplicadas mesmo sob concorrência e perante falhas. Todos os componentes executam em containers Docker, geridos com Docker Compose.

O modelo de faltas define os componentes que podem falhar, as garantias oferecidas, a deteção, a recuperação e a possível perda de informação, e será validado experimentalmente com falhas provocadas. Os pontos únicos de falha que subsistem na versão base (Nginx, Redis e broker MQTT) estão identificados, com mitigação e evolução previstas.

Nesta primeira fase foram realizadas a análise e a conceptualização: requisitos, arquitetura, modelo de dados, segurança, formulação do CSP, modelo de faltas e plano de trabalho. As fases seguintes incluem a prototipagem (2.ª entrega, 15 de novembro de 2026) e a implementação e os testes finais (3.ª entrega, 20 de dezembro de 2026).

## c) Contexto

### Problema abordado

- **Concorrência:** pedidos simultâneos para a mesma sala e horário podem originar reservas duplicadas;
- **Autenticação fraca:** a dependência exclusiva da palavra-passe expõe o sistema ao roubo e à adivinhação de credenciais;
- **Indisponibilidade:** um servidor centralizado deixa o serviço totalmente indisponível quando falha, sobretudo em época de exames;
- **Ocupação ineficiente:** salas reservadas que ninguém utiliza.

### Motivação

As salas de estudo de uma universidade são um recurso escasso e muito procurado. O problema é adequado para integrar, de forma coerente, as quatro áreas do semestre: engenharia de software, segurança informática, sistemas distribuídos e inteligência artificial, cumprindo o requisito do briefing de propor uma solução distribuída que resolva uma necessidade real.

### Objetivos

1. Autenticar com palavra-passe e segundo fator (TOTP);
2. Conceber uma arquitetura distribuída sem pontos únicos de falha nas camadas de serviços e de dados;
3. Impedir reservas duplicadas, mesmo sob concorrência e falhas;
4. Validar e atribuir reservas com um algoritmo de Problema de Satisfação de Restrições (CSP);
5. Integrar check-in com dispositivos IoT (MQTT) e libertação automática de reservas não utilizadas;
6. Definir o modelo de faltas e demonstrá-lo com falhas provocadas;
7. Garantir a rastreabilidade das operações relevantes (auditoria);
8. Seguir uma metodologia ágil, com controlo de versões e artefactos auditáveis.

## d) Processo

### Metodologia

Metodologia ágil e iterativa, com ciclos curtos alinhados com as três entregas (11/10, 15/11 e 20/12 de 2026). Cada ciclo percorre as fases do briefing: análise e conceptualização, planeamento, prototipagem, implementação, teste e apresentação.

### Ferramentas

GitHub (ramo `main` só com as versões entregues, ramo `develop` para o trabalho diário, integração por pull request), ClickUp (uma lista por área e uma lista de marcos com as datas das entregas) e draw.io (diagramas).

### Tecnologias

Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL (replicação primário e réplica), Redis, Nginx, Streamlit, Eclipse Mosquitto (MQTT), ESP32, pyotp, python-constraint, Docker, Docker Compose, pytest e GitHub Actions.

### Estrutura da equipa

Equipa de quatro elementos, com uma área principal cada: segurança informática (serviço de autenticação), inteligência artificial e IoT (serviço de reservas, CSP e MQTT), sistemas distribuídos (infraestrutura, replicação e testes de falhas) e engenharia de software (interface, modelação e documentação). A integração e os testes de ponta a ponta são responsabilidade partilhada.

## e) Resultados

### Descrição da solução desenvolvida

Na 1.ª entrega (fase de análise e conceptualização) foi concebida a solução, ainda não implementada. O StudySpot é uma aplicação web em que o estudante se autentica com palavra-passe e código TOTP e submete pedidos de reserva, validados por um CSP. Um dispositivo IoT à porta da sala regista o check-in por MQTT, e as reservas sem check-in no prazo são libertadas. A arquitetura distribui o serviço de autenticação e o serviço de reservas por duas ou mais instâncias sem estado, atrás de um balanceador Nginx, com PostgreSQL replicado, Redis para sessões e locks e um broker MQTT, tudo em containers Docker. A consistência das reservas combina um lock distribuído, uma restrição única na base de dados e chaves de idempotência.

### Funcionalidades principais

- Registo e login com autenticação de dois fatores (TOTP);
- Reserva de salas com validação automática por CSP, recusa fundamentada e lista de espera;
- Check-in físico por dispositivo IoT e libertação automática de reservas não utilizadas;
- Cancelamento e consulta das próprias reservas; gestão de salas pelo administrador;
- Registo de auditoria das operações relevantes;
- Tolerância a faltas, demonstrada com falhas provocadas.

### Contributos relevantes

- Modelo de faltas com garantias e não-garantias explícitas;
- Consistência das reservas assente na base de dados (restrição única por slot), com o lock distribuído como otimização;
- Identificação dos pontos únicos de falha residuais (Nginx, Redis e broker MQTT), com mitigação e evolução previstas;
- Formulação do CSP com exemplo trabalhado e critérios de avaliação.

## f) Reflexão

### Lições aprendidas

- Definir primeiro as garantias que o sistema oferece e só depois escolher os mecanismos que as cumprem;
- Um lock distribuído reduz a contenção, mas só uma restrição na base de dados garante a correção;
- A coerência entre relatório, slides e modelo de faltas exige revisão cruzada entre as áreas.

### Limitações

Instâncias únicas de Nginx, Redis e broker MQTT, promoção manual do primário do PostgreSQL, dispositivos IoT possivelmente simulados, demonstração local.

### Trabalho futuro

 Prototipar os serviços, a infraestrutura e o CSP (2.ª entrega, 15/11/2026); implementar o check-in e a libertação automática, avaliar experimentalmente o CSP e as falhas, e finalizar a documentação (3.ª entrega, 20/12/2026).
