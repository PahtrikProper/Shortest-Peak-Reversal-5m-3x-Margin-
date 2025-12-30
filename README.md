# Shortest Peak Reversal – 3m, 3x Margin

A short-biased peak-reversal strategy that backtests a highest-high breakdown on 3m candles, saves the best parameters, and (optionally) runs a live trading loop. The interactive package prompts you for the USDT pair you want to trade and runs end-to-end.

## Repository layout
- `src/your_short_trade_margin_call/` – interactive strategy package (prompts for USDT pair, runs backtests + live/paper loop, stores artifacts under `data/your/`).
- `data/` – runtime artifacts shared by the engines (best params, optimization queue).
- `notes/` – research notes for the workflow (`notes/strategy_overview.md`).
- `tests/` – placeholder for future automated tests.

```
.
├── src/your_short_trade_margin_call/   # Interactive strategy package (backtest + optimizer + live runner)
├── data/                               # JSON artifacts produced at runtime (per-symbol under data/your/)
├── notes/                              # Strategy notes
└── tests/                              # (empty placeholder)
```

## Entry points
Set `PYTHONPATH=src` from the repository root, then run:

- Interactive optimize → live loop (prompts for USDT pair, e.g., BTCUSDT):
  ```bash
  PYTHONPATH=src python -m your_short_trade_margin_call
  ```

## Behavior overview
- `BacktestEngine` sweeps `highest_high_lookback`, exit types, risk fractions, and take-profit candidates to find the best-performing parameters.
- `MainEngine` coordinates optimization, persists `data/your/best_params.json`, and enqueues new runs (12h cadence).
- `LiveTradingEngine` streams Bybit klines, applies the short breakout logic, and manages exits/margin calls for the chosen symbol.
- Backtests simulate the same microstructure as paper/live trading: spread + slippage on fills, random rejects, fee debits, leverage clamping, liquidation checks, structured exits, a Bybit-like cap on available balance usage, and verbose logging of blocked trades. Live paper fills use the current mid price by default. Defaults target ~24 hours of 3m Bybit futures data, with re-optimization queued every ~12 hours.
- `paths.py` centralizes repository and `data/` paths so artifacts land in a single shared folder (`data/your/`).

## Getting started
1. Create a Python virtual environment (e.g., `python -m venv .venv`) and activate it.
2. Install dependencies when they are defined (for example, via `pip install -r requirements.txt`).
3. Run the interactive entry point (`python -m your_short_trade_margin_call`) to optimize then start the trading loop.

## Notes
- Outputs land in `data/your/best_params.json` and `data/your/optimization_queue.json`; the folder is created automatically if missing.
- The strategy is experimental—paper trade first and understand the risks of leveraged trading.

For a conceptual overview of the workflow, see `notes/strategy_overview.md`.
