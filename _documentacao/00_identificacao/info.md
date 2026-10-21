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

8. **Palavras-chave:** reserva de salas, sistemas distribuídos, tolerância a faltas, segurança informática, autenticação de dois fatores, TOTP, inteligência artificial, CSP, IoT, MQTT, replicação, Docker.

9. **Tecnologias utilizadas:** Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Nginx, Streamlit, Eclipse Mosquitto (MQTT), ESP32, pyotp, python-constraint, Docker, Docker Compose, GitHub, ClickUp.

10. **Resumo curto:**

O StudySpot é um sistema distribuído de reserva de salas de estudo universitárias, com autenticação de dois fatores (TOTP), validação automática de pedidos por Inteligência Artificial (Problema de Satisfação de Restrições) e check-in físico com dispositivos IoT via MQTT. A arquitetura é tolerante a faltas: serviços de autenticação e de reservas em várias instâncias atrás de um balanceador Nginx, base de dados PostgreSQL replicada, e Redis para sessões e locks distribuídos, tudo em containers Docker. A consistência impede reservas duplicadas, mesmo sob concorrência e falhas, através de locks, restrições na base de dados e chaves de idempotência. O projeto integra Engenharia de Software, Segurança Informática, Sistemas Distribuídos e Inteligência Artificial, e demonstra a tolerância a faltas com falhas provocadas.