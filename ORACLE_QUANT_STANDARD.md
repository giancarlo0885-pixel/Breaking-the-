# Oracle Quantitative Trade Standard

GARIBALDI MARKET ORACLE remains a trading-first platform. This standard improves trade selection by requiring the forecasted edge to survive execution costs and portfolio risk.

## Core formula

```text
Trade Quality = 35% Alpha + 25% Execution + 25% Risk + 15% Relative Value
```

A trade is approved only when all gates pass:

```text
Trade Quality >= QUANT_MIN_QUALITY
Net Expected Value >= QUANT_MIN_NET_EV_PCT
Spread <= QUANT_MAX_SPREAD_PCT
Slippage <= QUANT_MAX_SLIPPAGE_PCT
Adverse Selection < 70
```

Expected value is calculated after estimated spread, slippage, fees, and market impact:

```text
Gross EV = P(win) × expected gain - P(loss) × expected loss
Net EV   = Gross EV - spread - slippage - fees - market impact
```

## Four scores

- **Alpha:** signal strength, confidence, trend, momentum, news, and model agreement.
- **Execution:** volume, liquidity, spread, slippage, market impact, and order-book imbalance when available.
- **Risk:** volatility, ATR, market regime, event risk, and portfolio concentration.
- **Relative value:** strength versus competing assets, sector/benchmark relationships, volume confirmation, and sentiment.

## Position sizing

Approved positions are scaled by the quantitative assessment. Better quality and higher net expected value receive more capital; elevated adverse-selection risk receives less.

```text
Trade Value = Maximum Allowed Trade × Signal Strength × Quant Position Multiplier
```

## Railway variables

```text
ENABLE_QUANT_TRADE_STANDARD=true
QUANT_MIN_QUALITY=68.0
QUANT_MIN_NET_EV_PCT=0.001
QUANT_MAX_SPREAD_PCT=0.006
QUANT_MAX_SLIPPAGE_PCT=0.005
QUANT_ADVERSE_REJECT_SCORE=70.0
```

Defaults are deliberately aggressive enough for the current paper-trading project while still filtering structurally poor trades. Tighten the thresholds only after collecting enough forward-test results.
