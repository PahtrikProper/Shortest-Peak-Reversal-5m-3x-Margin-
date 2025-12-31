# ChoCH/BOS Strategy Notes

## High-level workflow (live short trader + ChoCH/BOS)
- **Data sourcing:** Each package’s `DataClient` pulls Bybit klines using the configured symbol, category, and aggregation interval. Defaults: `BTCUSDT` on linear futures with 3m bars for the short trader; `BTCUSDT`/`SOLUSUT` spot with 1m bars for the ChoCH/BOS variants (override via each package’s `TraderConfig`).
- **Backtesting and optimization:** `MainEngine` invokes `BacktestEngine.grid_search_with_progress` against each strategy’s parameter grid (SMA/Stoch/MACD for the short trader; swing/Fibonacci/demand for ChoCH/BOS). The best configuration is saved to `data/best_params.json` under each package’s `data` folder.
- **Queueing future runs:** `OptimizationQueue` appends each optimization summary to `data/optimization_queue.json`, targeting a 2‑day cadence for reruns.
- **Live trading loops:** 
  - `LIVE_short_trader_multi_filter` reuses optimized parameters, streams fresh klines, and submits **live Bybit futures shorts** via the official client in `bybit_official_git_repo_scripts`. Wallet balance and open positions are read from the Unified account each bar to keep equity sizing accurate. Orders are limit-only: sells at current price (or best ask if lower) with TP, and reduce-only buys at current price to close, using isolated margin (`marginMode=ISOLATED_MARGIN`, `positionIdx=1`).
  - `choch_bos_strategy_btc_live` and `choch_bos_strategy_sol_live` reuse optimized parameters, stream fresh klines, and manage the trade lifecycle via `LiveTradingEngine` with `BuyOrderEngine`/`SellOrderEngine`.
- **Margin/leverage:** Short trader uses a configurable desired leverage (default 3x) and pulls wallet/position state from the unified account; ChoCH/BOS live variants set Bybit **isolated mode (tradeMode=1) with 10x leverage** using `/v5/position/set-leverage`. Adjust in each package’s `config.py`/`live.py` if your account requires different settings.
- **Mainnet vs testnet:** Short trader supports `testnet=True` for validation; ChoCH/BOS live variants default to mainnet. Ensure API keys and margin are present for the chosen environment.
- **Post-backtest menu / confirmation:** ChoCH/BOS live CLIs prompt for confirmation after backtest; short trader transitions directly into the live loop once parameters are selected.

## Strategy logic (long bias)
1. Build 15m swing highs/lows from aggregated data.
2. Compute Fibonacci pullback band between `fib_low` and `fib_high` of the swing range.
3. Require 1m ChoCH + BOS confirmation and demand alignment inside the Fibonacci band.
4. Enter when price taps the upper bound of the fib zone; exit on fib breakdown or demand loss.
5. Apply simulated fees, spread, slippage, and liquidation checks using `order_utils` (includes Bybit-style fee model and liquidation math).

## Strategy logic (short-only multi-filter)
- Filters: SMA on close, centered Stoch %K (smoothed), optional MACD/Signal confirmation, date-gate to avoid early history.
- Entry (short): consecutive higher lows failing (low[t-3] ≤ low[t-2] and low[t] < low[t-1]), SMA[t] < SMA[t-1], MACD/Signal if enabled, flat position.
- Exit: fixed 0.4% take-profit priority; optional momentum exit when Stoch K rises; margin-call guard via liquidation approximation.
- Live execution: market Sell with TP (LastPrice trigger), reduce-only market Buy to close, one position at a time, state synced from Bybit Unified account.

## Components and entry points
- **Optimizer + orchestration:** `main_engine.py` within each package (e.g., `src/LIVE_short_trader_multi_filter/main_engine.py`, `src/ChoCH-BOS-strategy-BTC-LIVE/choch_bos_strategy_btc_live/main_engine.py`).
- **Backtester:** `backtest_engine.py` within each package.
- **Live trading loop:** `live.py` within the live packages.
- **Order helpers:** `order_utils.py` within each package.
- **Paths and artifacts:** `paths.py` in every package keeps outputs in `data/`.

## Key artifacts
- `data/best_params.json`: latest optimized parameter set and summary metrics (per package).
- `data/optimization_queue.json`: queue of scheduled optimizer reruns (per package).

## Quickstart commands
- Short trader live: `PYTHONPATH=src python -m LIVE_short_trader_multi_filter` (set `BYBIT_API_KEY`/`BYBIT_API_SECRET`; use `testnet=True` in `TraderConfig` to validate).
- Short trader optimizer + live: `PYTHONPATH=src python -m short_trader_multi_filter`
- BTC live: `PYTHONPATH=src/ChoCH-BOS-strategy-BTC-LIVE python -m choch_bos_strategy_btc_live`
- SOL live: `PYTHONPATH=src/ChoCH-BOS-strategy-SOL-LIVE python -m choch_bos_strategy_sol_live`
- BTC paper trader: `PYTHONPATH=src/ChoCH-BOS-strategy-BTC-PAPER-TRADER python -m choch_bos_strategy_btc_paper_trader`
- SOL paper trader: `PYTHONPATH=src/ChoCH-BOS-strategy-SOL-PAPER-TRADER python -m choch_bos_strategy_sol_paper_trader`
