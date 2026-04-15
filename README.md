# Bot Telegram de Vendas

Este projeto roda um bot de vendas no Telegram com suporte a pagamentos via SillientPay ou MercadoPago e webhook FastAPI.

## Deploy gratuito sugerido

### Opção recomendada: Railway ou Render
1. Crie uma conta no Railway ou Render.
2. Crie um novo projeto / serviço Python.
3. Suba este repositório.
4. Configure as variáveis de ambiente usando `.env.example`:
   - `BOT_TOKEN`
   - `BASE_URL` (URL pública do serviço, ex: `https://meu-bot.up.railway.app`)
   - `PORT` (fornecido pelo serviço, ou use `8002`)
   - `MP_ACCESS_TOKEN` / `SILLIENTPAY_API_KEY` se usar pagamentos reais
5. O serviço deve iniciar com o comando do `Procfile`:
   - `web: python bot.py`

### Variáveis de ambiente
- `BOT_TOKEN`: token do BotFather
- `BASE_URL`: URL pública do app
- `WEBHOOK_URL`: opcional; se não for definido, usa `BASE_URL`
- `PORT`: porta do servidor (geralmente fornecida pelo provedor)
- `DATABASE_URL`: URL do banco de dados (padrão SQLite local)

## Como funciona
- O bot usa **polling** para o Telegram
- O FastAPI roda em background na mesma aplicação
- O webhook do SillientPay recebe eventos em `/webhook/sillientpay`

## Teste local
1. Instale dependências:
   ```bash
   pip install -r requirements.txt
   ```
2. Crie `.env` com as informações necessárias.
3. Rode:
   ```bash
   python bot.py
   ```
4. Verifique os endpoints:
   - `http://127.0.0.1:8002/health`
   - `http://127.0.0.1:8002/webhook/sillientpay`
