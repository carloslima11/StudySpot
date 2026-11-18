# Identificação do projeto

1. **Título:** StudySpot - Sistema distribuído de reserva de salas de estudo com 2FA e check-in IoT

2. **Ano letivo:** 2026/2027

3. **Semestre:** 5º

4. **Curso envolvido:** Licenciatura em Engenharia Informática (IADE – Universidade Europeia)

5. **Unidades curriculares:** 
* Projeto de Desenvolvimento de Software; 
* Engenharia de Software; 
* Segurança Informática; 
* Sistemas Distribuídos; 
* Inteligência Artificial.

6. **Docentes:** 
* Rui Pascoal e Miguel Boavida (Projeto); 
* Rui Ramos (Engenharia de Software); 
* Sérgio Nunes e Pedro Brandão (Segurança Informática); 
* Pedro Rosa (Sistemas Distribuídos); 
* Samuel Gomes (Inteligência Artificial).

7. **Estudantes participantes (Grupo 6):** 
* Carlos Alexandre Avelino Lima – 20240740 – L-EIF - 26/27 - D02 – 20240740@iade.pt; 
* Filomeno João Chiquete Sabino – 20241963 – L-EIF - 26/27 - D02 – 20241963@iade.pt;
* Savio Netxitxi da Silva Casimira – 20240896 – L-EIF - 26/27 - D02 – 20240896@iade.pt;
* Daniel Alexandre Mbeya Paulo – 20240992 – L-EIF - 26/27 - D02 – 20240992@iade.pt.

8. **Palavras-chave:** reserva de salas, sistemas distribuídos, tolerância a faltas, replicação síncrona, idempotência, locks distribuídos, segurança informática, autenticação de dois fatores, TOTP, Argon2, inteligência artificial, CSP, IoT, MQTT, Docker.

9. **Tecnologias utilizadas:** Python 3.12, FastAPI, Flask, Flask-Session, Gunicorn, SQLAlchemy, Alembic, PostgreSQL 18 (primário e réplica síncrona), Redis 7, Nginx, Eclipse Mosquitto (MQTT), paho-mqtt, segno (QR Codes), argon2-cffi, PyOTP, cryptography (AES-GCM), pytest, Docker, Docker Compose, GitHub, ClickUp.

10. **Entregas:**
* 1.ª entrega (11/10/2026): análise e conceptualização;
* 2.ª entrega (15/11/2026): protótipo distribuído funcional;
* 3.ª entrega (20/12/2026): check-in IoT, realocação automática e versão final.

11. **Resumo curto:**

O StudySpot é um sistema distribuído de reserva de salas de estudo universitárias, com autenticação de dois fatores (TOTP), validação automática de pedidos por Inteligência Artificial (Problema de Satisfação de Restrições) e check-in físico com QR Code e MQTT. Na 2.ª entrega, o protótipo corre em Docker Compose: duas instâncias do serviço de autenticação e duas do serviço de reservas atrás de um Nginx com HTTPS, Redis para sessões, tentativas de login e locks, e PostgreSQL com um primário e uma réplica síncrona. A combinação de locks no Redis, restrição UNIQUE na base de dados e chaves de idempotência impede reservas duplicadas, mesmo sob concorrência e falhas. A tolerância a faltas foi demonstrada parando instâncias e a réplica com o sistema em funcionamento. O check-in por QR Code e MQTT e a libertação automática de reservas sem check-in já têm código e testes, mas ficam desligados por omissão até à 3.ª entrega.
