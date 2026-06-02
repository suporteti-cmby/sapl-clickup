# Guia de deploy — GitHub Actions

## Pré-requisito
Conta gratuita no GitHub: https://github.com/signup

---

## Passo 1 — Criar o repositório

1. Acesse https://github.com/new
2. Preencha:
   - **Repository name:** `sapl-clickup`
   - **Visibility:** Public ✅ (necessário para Actions gratuito)
   - Deixe as demais opções desmarcadas
3. Clique em **Create repository**

---

## Passo 2 — Subir os arquivos

No terminal da sua máquina, dentro da pasta `sapl-clickup`:

```bash
git init
git add .
git commit -m "feat: integração SAPL → ClickUp"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/sapl-clickup.git
git push -u origin main
```

Substitua `SEU_USUARIO` pelo seu usuário do GitHub.

---

## Passo 3 — Configurar os Secrets (suas chaves)

Os Secrets ficam **criptografados** no GitHub — não aparecem no código.

1. No repositório, clique em **Settings** (aba superior)
2. No menu lateral, clique em **Secrets and variables → Actions**
3. Clique em **New repository secret** para cada item abaixo:

| Nome do Secret          | Valor                                      |
|-------------------------|--------------------------------------------|
| `SAPL_BASE_URL`         | `https://sapl.bayeux.pb.leg.br`            |
| `CLICKUP_API_KEY`       | `pk_SUA_CHAVE_AQUI`                        |
| `CLICKUP_TEAM_ID`       | ID do workspace (obtido no setup)          |
| `LIST_SECRETARIA`       | ID da list (obtido após rodar setup)       |
| `LIST_COMISSOES`        | ID da list                                 |
| `LIST_PROCURADORIA`     | ID da list                                 |
| `LIST_GABINETES`        | ID da list                                 |
| `LIST_MESA_DIRETORA`    | ID da list                                 |
| `LIST_EXECUTIVO`        | ID da list                                 |
| `SMTP_HOST`             | Ex: `smtp.gmail.com` (opcional)            |
| `SMTP_PORT`             | `587` (opcional)                           |
| `SMTP_USER`             | Seu e-mail (opcional)                      |
| `SMTP_PASS`             | Senha de app do Gmail (opcional)           |
| `DESTINATARIOS_EMAIL`   | `email1@camara.pb.gov.br,email2@...`       |
| `TELEGRAM_BOT_TOKEN`    | Token do bot (opcional)                    |
| `TELEGRAM_CHAT_ID`      | ID do grupo/canal (opcional)               |

---

## Passo 4 — Rodar o setup do ClickUp (UMA VEZ)

1. No repositório, clique na aba **Actions**
2. No menu lateral, clique em **Setup inicial ClickUp**
3. Clique em **Run workflow**
4. No campo, digite `confirmar` e clique em **Run workflow**
5. Aguarde ~1 minuto e clique no run concluído
6. Baixe o artefato **clickup-ids-gerados** (arquivo JSON com os IDs das Lists)
7. Preencha os Secrets `LIST_*` com os IDs do JSON

---

## Passo 5 — Ativar a sincronização

1. Na aba **Actions**, clique em **SAPL → ClickUp Sync**
2. Clique em **Run workflow** para testar manualmente
3. Verifique os logs — deve mostrar matérias sendo criadas no ClickUp
4. Pronto! A partir daí roda automaticamente a cada 30 minutos

---

## Monitorando as execuções

- Aba **Actions** no GitHub mostra cada execução com status ✅ ou ❌
- Logs completos ficam disponíveis em cada run
- Artefato `sync-log-N` contém o log detalhado (retido por 30 dias)
- Em caso de falha, o GitHub envia e-mail automático para o dono do repositório

---

## Como obter o Team ID do ClickUp

1. Acesse `app.clickup.com`
2. Olhe a URL: `https://app.clickup.com/XXXXXXXXX/home`
3. O número na URL é o seu Team ID

---

## Agendamentos configurados

| Workflow              | Frequência                    | Horário BRT       |
|-----------------------|-------------------------------|-------------------|
| Sync principal        | A cada 30 minutos             | Contínuo          |
| Relatório diário      | Segunda a sexta               | 07:00             |
| Setup inicial         | Manual (apenas uma vez)       | —                 |
