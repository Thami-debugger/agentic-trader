# Agentic Trader

This project can run in two modes:

- Local continuous process (`python -m app.main`)
- Vercel scheduled cycles (Cron triggers one cycle per invocation)

## Local run

Use the virtual environment Python and run as a module:

```powershell
& "c:/Users/nkosi/My Projects/agentic-trader/.venv/Scripts/python.exe" -m app.main
```

For one safe cycle:

```powershell
$env:CONTINUOUS_TRADING='false'
$env:AUTO_TRADE='false'
& "c:/Users/nkosi/My Projects/agentic-trader/.venv/Scripts/python.exe" -m app.main
```

## Vercel deployment

Important platform note:

- Vercel does not support always-on background loops.
- Vercel runs this app as stateless serverless functions.
- Continuous behavior is emulated by Vercel Cron calling `/api/cron` repeatedly.
- MT5 trade execution is automatically disabled on Vercel (Linux environment).

### 1. Import project in Vercel

- Import this repo/project into Vercel.

### 2. Configure install command

Set Vercel Install Command to:

```bash
pip install -r requirements-vercel.txt
```

### 3. Set environment variables

Set at least these in Vercel Project Settings:

- `AUTO_TRADE=false`
- `CONTINUOUS_TRADING=false`
- `CRON_SECRET=<strong-random-secret>`

Optional:

- `OPENAI_API_KEY`
- `NEWS_API_KEY`
- `DEFAULT_SYMBOL`

### 4. Deploy

`vercel.json` is already configured to:

- Route all requests to `api/index.py`
- Schedule `GET /api/cron` every 5 minutes

### 5. Verify

- `GET /health` should return `ok: true`
- `GET /api/cron` with correct bearer token should run one cycle

Example authorized call:

```bash
curl -H "Authorization: Bearer <CRON_SECRET>" https://<your-domain>/api/cron
```

