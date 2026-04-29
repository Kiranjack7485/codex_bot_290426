# Crypto Scalping Bot - Phase 1

This project is a modular Python crypto scalping bot for Binance Futures that:

- Connects to Binance Futures real and demo environments simultaneously
- Scans `BTCUSDT`, `ETHUSDT`, `BNBUSDT`, `SOLUSDT`, `XRPUSDT`
- Evaluates strict 5m primary and 15m confirmation logic
- Executes trades only on Binance Futures demo trading
- Sends Telegram alerts for strong signals, demo trades, TP, SL, startup, sessions, and 30-minute scan status

## Strategy Rules Implemented

The bot enforces these conditions before execution:

- Market structure must align on both `5m` and `15m`
- Sideways structure returns `NO TRADE`
- Liquidity zones include:
  - Previous swing highs/lows
  - Equal highs/lows
  - Session highs/lows
- Setup logic covers:
  - Liquidity Sweep Reversal
  - Break and Retest
  - Trend Pullback
- Fair Value Gap alignment is required for setups
- Volume spike confirmation is required
- EMA `9` and `21` must align with direction
- Score must be at least `7`
- Second concurrent trade is allowed only at score `>= 8`

## File Structure

- [main.py](</C:/Users/DELL/OneDrive/Documents/New project/main.py>)
- [bot/config.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/config.py>)
- [bot/data_fetcher.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/data_fetcher.py>)
- [bot/strategy_engine.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/strategy_engine.py>)
- [bot/risk_manager.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/risk_manager.py>)
- [bot/execution_engine.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/execution_engine.py>)
- [bot/notifier.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/notifier.py>)
- [bot/models.py](</C:/Users/DELL/OneDrive/Documents/New project/bot/models.py>)
- [.env.example](</C:/Users/DELL/OneDrive/Documents/New project/.env.example>)

## Setup

1. Create and activate a virtual environment.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and fill in:

- `BINANCE_API_KEY`
- `BINANCE_SECRET`
- `BINANCE_TESTNET_API_KEY`
- `BINANCE_TESTNET_SECRET`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

4. Start the bot.

```powershell
python main.py
```

If you see `ModuleNotFoundError`, install dependencies first:

```powershell
pip install -r requirements.txt
```

If you see Binance `-2015 Invalid API-key, IP, or permissions for action`, verify all of the following:

- The real API key is a Binance Futures key with permission for futures account queries
- The demo API key is created for Binance Futures demo trading, not on production Binance
- `BINANCE_API_KEY` and `BINANCE_SECRET` belong to the same account
- `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_SECRET` belong to the same demo account
- Any IP restriction on the keys includes the machine running the bot
- Legacy CCXT sandbox mode is no longer supported for Binance USD-M futures; this bot uses demo trading mode instead

## How It Runs

- Real Binance Futures connection is used for market data scanning
- Binance Futures demo-trading connection is used for balance, leverage, and order execution
- Telegram notifications are limited to the required events only
- The scanner runs asynchronously across all five symbols
- Entry order logic:
  - Liquidity Sweep Reversal: market order
  - Break and Retest: limit order
  - Trend Pullback: limit order
- Trading is preferred only during these IST windows:
  - `09:00` to `12:30`
  - `18:30` to `22:30`

## Railway Deployment

1. Push this repository to GitHub.
2. Create a new Railway project from the GitHub repo.
3. Add the same environment variables from `.env.example` in Railway Variables.
4. Set the start command:

```bash
python main.py
```

5. Ensure the deployment uses Python 3.11 or newer.

Optional `Procfile` content:

```text
worker: python main.py
```

## Notes

- Strategy tuning values are exposed through environment variables so the logic stays explicit.
- Before live use, validate Binance demo-trading order type support for your account and region.
- This code is Phase 1 infrastructure and should be forward-tested extensively before any production capital is considered.
