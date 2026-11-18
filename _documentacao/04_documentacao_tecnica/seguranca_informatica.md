# Segurança informática — StudySpot

Código: `backend/auth_service/app/core/` (`security.py`, `sessions.py`, `ratelimit.py`) e `backend/auth_service/app/routes/auth.py`.

## 1. Autenticação

| Mecanismo | Implementação |
|---|---|
| Palavras-passe | Mínimo de 10 caracteres; guardadas com Argon2 (`argon2-cffi`), nunca em texto simples |
| Segundo fator | TOTP (RFC 6238, PyOTP) com aplicação autenticadora; segredo de 160 bits, configurado no registo com um QR Code e confirmado com um primeiro código |
| Cifragem do segredo TOTP | AES-GCM (`cryptography`) com nonce próprio; a chave (`TOTP_ENCRYPTION_KEY`, 256 bits) está no `.env`, fora da base de dados |
| Anti-reutilização | `utilizadores.ultimo_passo_totp`: um código de um passo igual ou anterior ao último aceite é rejeitado |
| Login em dois passos | `POST /api/auth/login` valida a palavra-passe e devolve um desafio (guardado no Redis durante 5 min); `POST /api/auth/login/totp` valida o código e cria a sessão |
| Limitação de tentativas | 5 falhas em 15 minutos, por email e por IP (guardados no Redis como hash SHA-256); depois responde 429 até a janela expirar |
| Mensagens de erro | Genéricas, para não revelar se o email existe |

## 2. Sessões

- Token aleatório de 256 bits (`secrets.token_urlsafe(32)`), guardado no Redis como `sessao:<token>`;
- Expira após 30 minutos sem atividade; cada pedido válido renova o prazo, até um máximo absoluto de 8 horas;
- O logout apaga a sessão no servidor;
- O serviço de reservas valida o mesmo token (cabeçalho `Authorization: Bearer`) diretamente no Redis partilhado;
- No browser só existe o cookie da sessão Flask, com `HttpOnly`, `Secure` e `SameSite=Lax`; o token do serviço de autenticação fica do lado do servidor.

## 3. Transporte

- O Nginx termina o TLS na porta 443 (publicada como 8443) e redireciona o HTTP com o código 308, que mantém o método do pedido;
- Em desenvolvimento é usado um certificado autoassinado ou gerado com `mkcert`;
- A comunicação entre o Nginx e os serviços ocorre na rede interna do Docker, sem TLS;
- As portas publicadas estão presas a `127.0.0.1`, por isso não ficam expostas à rede local.

## 4. Modelo de ameaças

| Ameaça | Mitigação | Risco residual |
|---|---|---|
| Força bruta ou *password spraying* | 5 tentativas em 15 min por email e IP; Argon2; segundo fator obrigatório | Ataques muito distribuídos por muitos IP |
| Roubo da base de dados | Hashes Argon2; segredos TOTP cifrados com chave fora da base de dados | Fuga simultânea da chave (`.env`) |
| Reutilização de um código TOTP intercetado | `ultimo_passo_totp` | Interceção e uso no mesmo passo de 30 s |
| Roubo ou fixação de sessão | Token de 256 bits no servidor; cookie `HttpOnly`, `Secure`, `SameSite`; expiração e logout | Malware no computador do utilizador |
| Escuta da rede | HTTPS com redirecionamento 308 | Certificado autoassinado; tráfego interno sem TLS |
| Enumeração de contas | Mensagem genérica no login | O registo pode revelar que um email já está registado |
| Pedido forjado entre sites (CSRF) | Cookie `SameSite=Lax`; alterações apenas por POST | Não há token CSRF nos formulários |
| Reservas duplicadas por repetição | `Idempotency-Key` e `UNIQUE` no PostgreSQL | — |
| Check-in falsificado «3.ª entrega» | QR com token HMAC-SHA256 por reserva e sala, válido 2 min | Captura e uso do QR dentro dos 2 min |
| Segredos no repositório público | `.env`, `.certs/` e `.venv/` no `.gitignore`; `.env.example` sem valores reais | Erro humano ao fazer commit |

## 5. Dados pessoais (RGPD)

O sistema guarda apenas o necessário: nome, email, perfil e histórico de reservas. Os prazos de conservação e o direito ao apagamento ficam definidos na versão final.

## 6. Por implementar

- Token CSRF nos formulários do cliente web;
- Auditoria das operações relevantes, só de acrescento e encadeada por hash;
- Códigos de recuperação;
- TLS entre o Nginx e os serviços, se o sistema sair do ambiente local.
