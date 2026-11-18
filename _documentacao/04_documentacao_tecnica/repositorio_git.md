# Repositório Git

- **URL:** https://github.com/carloslima11/StudySpot.git
- **Visibilidade:** público. 
- **Gestão do projeto:** ClickUp.

## Branch

| Branch | Uso |
|---|---|
| `main` | Versões entregues, integradas por pull request |
| `develop` | Trabalho diário e integração das funcionalidades |



## Estrutura

```
StudySpot/
├── backend/
│   ├── auth_service/        Serviço de autenticação (FastAPI): registo, TOTP, login, sessões
│   └── booking_service/     Serviço de reservas (FastAPI): salas, reservas, CSP, locks, check-in
│       ├── app/csp.py       Motor CSP (componente de IA)
│       └── scripts/         Leitor de QR simulado (dispositivo de check-in)
├── frontend/
│   └── web_client/          Cliente web (Flask): páginas, rotas e chamadas às APIs
├── database/
│   ├── migrations/          Migrações Alembic das tabelas de autenticação
│   ├── postgres/            Scripts e pg_hba.conf da replicação
│   └── schema.sql           Esquema de referência da 1.ª entrega (não usado no arranque)
├── nginx/nginx.conf         Proxy reverso, TLS e balanceamento
├── mosquitto/               Configuração do broker MQTT
├── docker-compose.yml       Todos os serviços
├── alembic.ini              Configuração das migrações
├── .env.example             Modelo das variáveis de ambiente
└── _documentacao/           Documentação, conforme o briefing
    ├── 00_identificacao/        Identificação do projeto
    ├── 01_memoria_descritiva/   Memória descritiva
    ├── 02_imagens/              Diagramas e capturas do protótipo
    ├── 03_videos/               Vídeos de demonstração
    ├── 04_documentacao_tecnica/ Relatórios, apresentações e documentos técnicos
    ├── 05_artefactos/           Artefactos entregáveis
    ├── 06_dados_investigacao/   Dados de investigação e medições
    └── 07_Autorizacoes/         Autorizações
```


