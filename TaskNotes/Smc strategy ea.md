# SMC Strategy Expert Advisor (XAUUSD)

## Overview
Smart Money Concepts (SMC) based Expert Advisor for XAUUSD trading on MetaTrader 5.

## Key Components

### 1. Market Structure
- **Fractal Swing Detection**: Identify highs/lows
- **Break of Structure (BOS)**: Entry signals when price breaks key levels
- **Change of Character (CHoCH)**: Trend reversal signals

### 2. Liquidity Management
- **Liquidity Sweep**: Detect when price sweeps above/below recent extremes
- **Order Block (OB)**: Support/resistance zones from institutional buying/selling
- **Fair Value Gaps (FVG)**: Imbalance zones for pullback entries

### 3. Position Management
- **ATR-based Stops**: Dynamic stop-loss using Average True Range
- **Risk-Reward Ratio**: 1:2 minimum for all trades
- **Position Sizing**: Kelly Criterion or fixed % of account

### 4. Entry Signals
- Price forms BOS at key level + confirmation
- Liquidity sweep followed by pullback to FVG
- Order block rejection with impulse move
- Confluence of multiple SMC signals

## Current Implementation Status
- [x] Fractal detection
- [x] BOS identification
- [x] Sweep detection
- [ ] FVG mapping
- [ ] Order block analysis
- [ ] Advanced filtering

## TODO
- [ ] Backtest on 1H timeframe (2023-2025 data)
- [ ] Optimize entry filters
- [ ] Add multiple timeframe confirmation
- [ ] Implement drawdown protection
