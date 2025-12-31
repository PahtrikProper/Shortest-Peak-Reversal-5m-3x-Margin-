# Short Trader Multi Filter – 3m, ~10x, 95% Funds (interactive)

This repository publishes a single active strategy: **short_trader_multi_filter**. All other legacy strategies have been moved under `archived_strategies/`. The active strategy backtests a short-only, multi-filter setup (centered Stoch, SMA, optional MACD/Signal) on 3m candles over ~3 hours of history, locks a 0.4% take-profit, and can run a live Bybit futures loop for a USDT pair you choose at startup.

## Repository layout
- `src/short_trader_multi_filter/` – interactive strategy package (prompts for USDT pair, runs backtests, stores artifacts under `data/multi_filter/`).
- `src/LIVE_short_trader_multi_filter/` – **live Bybit futures** variant that reuses the optimizer, syncs equity/positions via the official Bybit HTTP client (see `bybit_official_git_repo_scripts/`), and submits live short orders.
- `bybit_official_git_repo_scripts/` – upstream Bybit client and examples used for live trading (HTTP, websocket, position, account helpers, etc.).
- `archived_strategies/` – legacy/retired strategy folders (currently empty).
- `data/` – runtime artifacts produced at execution (per-symbol under `data/multi_filter/`; defaults include `best_params.json`, `optimization_queue.json`).
- `notes/` – strategy notes and quickstart references.
- `tests/` – placeholder.

```
.
├── src/
│   ├── short_trader_multi_filter/        # Interactive strategy package (backtest + optimizer)
│   └── LIVE_short_trader_multi_filter/   # Live Bybit futures executor (uses official client)
├── bybit_official_git_repo_scripts/      # Official Bybit HTTP/WebSocket client & examples
├── archived_strategies/                  # Legacy/retired strategies (empty)
├── data/                                 # JSON artifacts produced at runtime (per-symbol under data/multi_filter/)
├── notes/                                # Strategy notes and quickstarts
└── tests/                                # (empty placeholder)
```

## Entry points
Set `PYTHONPATH=src` from the repository root, then run the optimizer + live launcher:

```bash
PYTHONPATH=src python -m short_trader_multi_filter
```
You will be prompted for a USDT pair (e.g., BTCUSDT). The app backtests ~3 hours of 3m Bybit **linear futures** data, selects the best parameters from the configured grid, and saves artifacts under `data/multi_filter/`.

To run the live Bybit futures executor with your saved parameters and API keys (unified account, linear category):

```bash
export BYBIT_API_KEY=your_key
export BYBIT_API_SECRET=your_secret
PYTHONPATH=src python -m LIVE_short_trader_multi_filter
```
Set `testnet=True` in `TraderConfig` if you want to validate flows on Bybit testnet first. The live loop uses the official client in `bybit_official_git_repo_scripts` for wallet/position reads and order submission.

### Runtime configuration (key fields in `TraderConfig`)
- `symbol` / `category`: defaults to `BTCUSDT` / `linear`.
- `api_key` / `api_secret` / `testnet`: injected from env or edited in `config.py`. Use a Unified account key.
- `settlement_coin`: `USDT` by default.
- `time_in_force`: `IOC` by default for market orders with TP.
- `desired_leverage`: target leverage when sizing shorts (equity pull each bar keeps sizing honest).
- `risk_fraction` / `margin_rate`: control position sizing and liquidation buffer.
- Strategy knobs: `sma_period`, `stoch_period`, `smooth_k`, `macd_fast/slow/signal`, `use_macd`, `use_signal`, `use_momentum_exit`.

### Data and artifacts
- Backtests fetch Bybit REST klines from `/v5/market/kline` (linear category) for the configured window/interval.
- Optimizer and live artifacts are saved under `data/multi_filter/` (e.g., `best_params.json`).

## Behavior overview
- Filters: SMA on close, centered Stoch %K (smoothed), optional MACD and Signal. Date filter blocks entries before the configured start year/month.
- Entry (short only, one position at a time):
  - in-date, low[t-2] ≤ low[t-1] and low[t] < low[t-1]; SMA[t] < SMA[t-1]; MACD/Signal filters if enabled; flat position.
  - Size: 95% of equity with 10% margin requirement (≈9.5–10x notional), commission/slippage off.
- Exits: TP at 0.4% (priority), optional momentum exit when Stoch K rises; one full exit, no pyramiding.
- Live loop: runs immediately after backtest, fetches 3m bars, applies the same filters, and submits/monitors **live Bybit futures short orders**:
  - **Sell**: limit at the current last price, using best ask only if it is lower; TP attached.
  - **Buy to close**: reduce-only limit at the current last price (no bid override).
  - Orders include `marginMode=ISOLATED_MARGIN` and `positionIdx=1` (one-way short). Equity/position snapshots are pulled from Bybit each bar to keep state in sync.
- Backtests use ~3 hours of 3m Bybit futures data; optimizer grid is defined in `config.py`.

## Notes
- Outputs land in `data/multi_filter/best_params.json` and related artifacts; the folder is created automatically.
- The strategy is experimental—paper trade or use Bybit testnet first and understand the risks of leveraged trading. Live trading requires correct API keys and sufficient margin in your unified account.
