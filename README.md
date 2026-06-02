# SAPL → ClickUp | Câmara Municipal de Bayeux

Sistema de integração automática entre o **SAPL** (Sistema de Apoio ao Processo Legislativo) e o **ClickUp**, com alertas de prazos e tramitações.

---

## Estrutura do projeto

```
sapl-clickup/
├── config/
│   └── .env.example        # Modelo de configuração (copie para .env)
├── src/
│   ├── setup_clickup.py    # Roda UMA VEZ para criar estrutura no ClickUp
│   ├── sapl_client.py      # Acesso à API REST do SAPL
│   ├── clickup_client.py   # Acesso à API do ClickUp
│   ├── prazos.py           # Motor de cálculo de prazos em dias úteis
│   ├── alertas.py          # Alertas por e-mail e Telegram
│   └── sync.py             # Script principal de sincronização
├── logs/
│   └── sync.log            # Gerado automaticamente
└── requirements.txt
```

---

## Instalação

```bash
# 1. Clonar / copiar o projeto
cd sapl-clickup

# 2. Criar ambiente virtual (recomendado)
python3 -m venv venv
source venv/bin/activate       # Linux/Mac
# ou: venv\Scripts\activate    # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Configurar variáveis de ambiente
cp config/.env.example config/.env
# Edite o arquivo .env com suas chaves
```

---

## Configuração inicial (rodar UMA VEZ)

Este script cria toda a estrutura no ClickUp (Space, Folder, Lists, campos customizados):

```bash
cd src
python setup_clickup.py --api-key pk_SUA_CHAVE --team-id SEU_TEAM_ID
```

Como obter o `team-id`:
- Acesse `app.clickup.com`
- Vá em Configurações → Workspace
- O ID aparece na URL: `app.clickup.com/XXXXXXXX/...`

Após rodar, copie os IDs gerados para o `.env`.

---

## Uso

### Sincronização única (teste)
```bash
cd src
python sync.py
```

### Modo daemon (produção — roda continuamente)
```bash
python sync.py --modo daemon
```

### Apenas alertas (sem sincronizar tarefas)
```bash
python sync.py --apenas-alertas
```

---

## Agendamento automático (Linux — cron)

Edite o crontab para sincronizar a cada 30 minutos:

```bash
crontab -e
```

Adicione a linha:
```
*/30 * * * * /caminho/para/venv/bin/python /caminho/para/sapl-clickup/src/sync.py >> /caminho/para/sapl-clickup/logs/cron.log 2>&1
```

---

## Agendamento no Windows (Task Scheduler)

1. Abra o **Agendador de Tarefas**
2. Crie uma nova tarefa básica
3. Disparador: **Diariamente**, repetir a cada **30 minutos**
4. Ação: iniciar programa
   - Programa: `C:\caminho\venv\Scripts\python.exe`
   - Argumentos: `C:\caminho\sapl-clickup\src\sync.py`

---

## Alertas por Telegram (opcional)

1. Crie um bot pelo [@BotFather](https://t.me/BotFather) no Telegram
2. Copie o token gerado para `TELEGRAM_BOT_TOKEN` no `.env`
3. Adicione o bot ao grupo/canal desejado
4. Obtenha o `chat_id` em: `https://api.telegram.org/botSEU_TOKEN/getUpdates`

---

## Hospedagem recomendada (gratuita/barata)

| Opção | Custo | Observação |
|-------|-------|-----------|
| **Railway** | ~$5/mês | Mais simples, deploy em 2 minutos |
| **Render** | Grátis (com limitações) | Para uso leve |
| **Servidor da Câmara** | Já existe | Ideal se houver VPS Linux disponível |
| **Computador local** | Grátis | Só funciona com o computador ligado |

---

## Personalização de prazos

Edite o arquivo `src/prazos.py`, seção `PRAZOS_POR_TIPO`:

```python
PRAZOS_POR_TIPO = {
    "PL":  20,   # Projeto de Lei — 20 dias úteis
    "REQ":  5,   # Requerimento — 5 dias úteis
    # Adicione conforme o Regimento Interno da Câmara
}
```

---

## Suporte

Em caso de dúvidas, abra uma issue ou entre em contato com a equipe de TI da Câmara.
