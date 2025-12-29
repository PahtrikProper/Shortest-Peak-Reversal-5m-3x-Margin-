# Shortest Peak Reversal – 5m, 3x Margin

A short-biased peak-reversal strategy that backtests a highest-high breakdown on 5m candles, saves the best parameters, and (optionally) runs a live trading loop. This repository contains a single strategy package plus its supporting data and notes.

## Repository layout
- `src/short_trade_margin_call/` – the strategy package (backtests, optimizer, live/paper trade entry points).
- `data/` – runtime artifacts shared by the engines (`best_params.json`, `optimization_queue.json`).
- `notes/` – research notes for the workflow (`notes/strategy_overview.md`).
- `tests/` – placeholder for future automated tests.
- `Shortest-Peak-Reversal-5m-3x-Margin-.zip` – original bundle of the extracted files.

```
.
├── src/short_trade_margin_call/    # Strategy package (backtest + optimizer + live runner)
├── data/                           # JSON artifacts produced at runtime
├── notes/                          # Strategy notes
└── tests/                          # (empty placeholder)
```

## Entry points
Set `PYTHONPATH=src` from the repository root, then run one of the following:

- Orchestrated optimize → live loop:
  ```bash
  PYTHONPATH=src python -m short_trade_margin_call
  # equivalent:
  PYTHONPATH=src python -m short_trade_margin_call.start
  ```
- Backtest/optimization only:
  ```bash
  PYTHONPATH=src python -m short_trade_margin_call.backtest_engine
  ```
- Live trading using previously saved params:
  ```bash
  PYTHONPATH=src python -m short_trade_margin_call.live
  ```

## Behavior overview
- `BacktestEngine` sweeps `highest_high_lookback` and exit-type candidates to find the best-performing parameters.
- `MainEngine` coordinates optimization, persists `data/best_params.json`, and enqueues new runs in `data/optimization_queue.json`.
- `LiveTradingEngine` streams Bybit klines, applies the short breakout logic, and manages exits/margin calls.
- Backtests simulate the same microstructure as paper/live trading: spread + slippage on fills, random rejects, fee debits, leverage clamping, liquidation checks, structured exits, and a Bybit-like cap on available balance usage (risk is capped at the configured maximum fraction). Live paper fills use the current mid price by default.
- `paths.py` centralizes repository and `data/` paths so artifacts land in a single shared folder.

## Getting started
1. Create a Python virtual environment (e.g., `python -m venv .venv`) and activate it.
2. Install dependencies when they are defined (for example, via `pip install -r requirements.txt`).
3. Update `TraderConfig` in `src/short_trade_margin_call/config.py` for your symbol, leverage, and slippage/spread assumptions.
4. Run the orchestrated entry point (`python -m short_trade_margin_call`) to optimize then start the trading loop, or run the specific modules listed above as needed.

## Notes
- Outputs land in `data/best_params.json` and `data/optimization_queue.json`; the folder is created automatically if missing.
- The strategy is experimental—paper trade first and understand the risks of leveraged trading.

For a conceptual overview of the workflow, see `notes/strategy_overview.md`.
