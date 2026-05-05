# Crypto Scalp Signal Bot

This project is dedicated only to crypto scalp trading signals.

It does not scan Indian stocks, Indian indices, options, or any non-crypto market.
It does not execute trades.
It only sends high-probability crypto scalp alerts to Telegram.

## Sessions

The bot scans crypto only during these IST windows:

- Indian market hours crypto session: `09:15` to `10:30`
  - extra care and confirmation
  - stricter score threshold
  - liquidity sweep can be required
- US/London overlap: `18:30` to `22:30`
  - primary high-probability crypto session

Outside these windows the bot stays idle and sends nothing.

## Strategy

Symbols:

- `BTCUSDT`
- `ETHUSDT`
- `BNBUSDT`
- `SOLUSDT`
- `XRPUSDT`

Timeframes:

- `5m`
- `15m`

Mandatory conditions:

- Market structure: `HH/HL` or `LH/LL`
- Liquidity sweep before entry
- Fair Value Gap alignment
- Volume spike confirmation
- EMA `9` and `21` alignment

Scoring:

- Liquidity sweep: `+3`
- Market structure: `+3`
- EMA alignment: `+2`
- Volume spike: `+2`

Base signal floor:

- `score >= 7`

Session filtering:

- Indian market hours session: stricter, default `score >= 9`
- US/London overlap: strong, default `score >= 8`

## Reversal Alerts

After a signal is sent, the bot keeps watching that symbol and sends a reversal alert only when all are confirmed:

- opposite structure formation
- strong reversal candle
- opposite-direction volume spike
- EMA crossover against the prior direction

## Project Layout

- `main.py` - crypto-only session controller
- `bot/config.py` - crypto and Telegram configuration
- `bot/data_fetcher.py` - Binance futures market data client
- `bot/crypto_scanner.py` - crypto scan orchestration
- `bot/strategy_engine.py` - crypto strategy engine
- `bot/reversal_engine.py` - confirmed reversal detection
- `bot/notifier.py` - Telegram alerts
- `bot/models.py` - crypto signal models

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

## Environment

Required:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Optional:

- `BINANCE_API_KEY`
- `BINANCE_SECRET`

## Run

```powershell
python main.py
```

## Deploy

Use the included `Dockerfile` or deploy directly on Railway or a VPS with the required environment variables.
