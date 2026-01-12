# TradingBot — Binance Futures Testnet

Simple trading bot that places MARKET / LIMIT / STOP_LIMIT orders on Binance Futures Testnet using `python-binance`.

**Files**
- **trading_bot.py**: Main bot and CLI.
- **config.py**: Optional local key file (not recommended for production).

**Requirements**
- Python 3.10+ (project venv recommended)
- `python-binance` library

**Setup (PowerShell)**
```powershell
# from project root
python -m venv env
.\env\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install python-binance
```

If your venv already exists, run commands with the venv python:
```powershell
.\env\Scripts\python.exe -m pip install python-binance
```

**API Keys**
- Recommended: set environment variables `BINANCE_TESTNET_API_KEY` and `BINANCE_TESTNET_API_SECRET`.
- Alternative: you can put testnet keys in [config.py](config.py), but avoid committing secrets.

PowerShell example:
```powershell
$env:BINANCE_TESTNET_API_KEY = 'your_testnet_key'
$env:BINANCE_TESTNET_API_SECRET = 'your_testnet_secret'
```

**Run the bot**
- MARKET order (no auto-adjust):
```powershell
.\env\Scripts\python.exe trading_bot.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
```

- MARKET order with automatic quantity adjustment to meet minimum notional:
```powershell
.\env\Scripts\python.exe trading_bot.py --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001 --auto-adjust
```

- LIMIT order:
```powershell
.\env\Scripts\python.exe trading_bot.py --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 30000
```

- STOP_LIMIT order:
```powershell
.\env\Scripts\python.exe trading_bot.py --symbol BTCUSDT --side SELL --type STOP_LIMIT --quantity 0.001 --price 30000 --stop-price 30500
```

**Behavior notes**
- The bot checks symbol `MIN_NOTIONAL` and `LOT_SIZE` filters before placing market orders and will return a clear error if the requested quantity is too small.
- With `--auto-adjust` the bot increases quantity to the smallest valid step that satisfies the min-notional requirement.
- The script sets the Binance Futures Testnet base URL and uses the `futures_` endpoints from `python-binance`.

**Troubleshooting**
- Import / Pylance warnings: make sure VS Code uses the project's `env\Scripts\python.exe` interpreter.
- If `pip` launcher fails, run `python -m pip ...` using the venv python as shown above.
- API key errors:
  - `API-key format invalid` — ensure you are using Futures TESTNET keys (not mainnet) and no extra whitespace.
  - `Order's notional must be no smaller than 100` — increase quantity or use `--auto-adjust`.

**Security**
- Never commit live API keys. Use testnet keys for development. Prefer environment variables or a secrets manager.

**Files to inspect**
- See [trading_bot.py](trading_bot.py) for implementation details.
- See [config.py](config.py) for how keys are loaded (fallback only).

If you want, I can:
- Add a `requirements.txt` for the project.
- Always auto-adjust quantities (instead of requiring `--auto-adjust`).
- Add unit tests for the validation logic.

