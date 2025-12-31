# Short Trader Multi Filter – 3m, 3x Margin (interactive)

A short-only, multi-filter strategy that backtests a highest-low / momentum-style setup using centered Stoch, SMA, and optional MACD/Signal filters on 3m candles. It backtests ~3 hours of history, locks a 0.4% take-profit, and (optionally) runs a live loop for a USDT pair you choose at startup.

## Repository layout
- `src/short_trader_multi_filter/` – interactive strategy package (prompts for USDT pair, runs backtests, stores artifacts under `data/multi_filter/`).
- `data/` – runtime artifacts produced at execution (per-symbol under `data/multi_filter/`).
- `notes/` – strategy notes.
- `tests/` – placeholder.

```
.
├── src/short_trader_multi_filter/   # Interactive strategy package (backtest + optimizer)
├── data/                            # JSON artifacts produced at runtime (per-symbol under data/multi_filter/)
├── notes/                           # Strategy notes
└── tests/                           # (empty placeholder)
```

## Entry point
Set `PYTHONPATH=src` from the repository root, then run:

```bash
PYTHONPATH=src python -m short_trader_multi_filter
```
You will be prompted for a USDT pair (e.g., BTCUSDT). The app backtests ~3 hours of 3m futures data, selects the best parameters from the configured grid, and saves artifacts under `data/multi_filter/`.

## Behavior overview
- Filters: SMA on close, centered Stoch %K (SMoothed), optional MACD and Signal. Date filter blocks entries before the configured start year/month.
- Entry (short only, one position at a time):
  - in-date, low[t-2] ≤ low[t-1] and low[t] < low[t-1]; SMA[t] < SMA[t-1]; MACD/Signal filters if enabled; flat position.
  - Size: 95% of equity with 19% margin (≈5.26x notional), commission/slippage off.
- Exits: TP at 0.4% (priority), optional momentum exit when Stoch K rises; one full exit, no pyramiding.
- Backtests use ~3 hours of 3m Bybit futures data; optimizer grid is defined in `config.py`.

## Notes
- Outputs land in `data/multi_filter/best_params.json` and related artifacts; the folder is created automatically.
- The strategy is experimental—paper trade first and understand the risks of leveraged trading.
