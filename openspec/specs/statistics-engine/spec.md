# Statistics Engine Specification

## Purpose

Pure Python computation of standard trading performance metrics from backtest results. Operates on Pydantic models from the Result Reader with zero SQX dependency. Provides consistent, well-documented metric calculations.

## Requirements

### Requirement: Profit Factor

The system MUST compute Profit Factor as `gross_profit / abs(gross_loss)`. When gross_loss is zero, Profit Factor SHALL be reported as infinity.

#### Scenario: Normal profit factor calculation

- GIVEN a trade list with gross profit 15000 and gross loss 5000
- WHEN the engine computes Profit Factor
- THEN the result is 3.0

#### Scenario: Zero gross loss returns infinity

- GIVEN a trade list with all profitable trades (gross loss = 0)
- WHEN the engine computes Profit Factor
- THEN the result is `inf` (positive infinity)

### Requirement: Sharpe and Sortino Ratios

The system MUST compute Sharpe Ratio using risk-free rate (default 0) and annualized factor from trade frequency. Sortino Ratio MUST use downside deviation only.

#### Scenario: Sharpe computes from daily returns

- GIVEN a trade list with 252 daily returns
- WHEN the engine computes Sharpe Ratio
- THEN the result equals `mean(returns) / std(returns) * sqrt(252)`

#### Scenario: Sortino ignores upside volatility

- GIVEN a trade list with positive returns and some negative returns
- WHEN the engine computes Sortino Ratio
- THEN the denominator uses only negative return deviations, not all deviations

### Requirement: Maximum Drawdown

The system MUST compute maximum drawdown as the largest peak-to-trough decline in the equity curve, expressed as a positive percentage.

#### Scenario: Drawdown from equity curve

- GIVEN an equity curve peaking at 100000 and troughing at 75000
- WHEN the engine computes max drawdown
- THEN the result is 25.0%

#### Scenario: Monotonically increasing equity has zero drawdown

- GIVEN an equity curve with strictly increasing values
- WHEN the engine computes max drawdown
- THEN the result is 0.0%

### Requirement: MAR and Recovery Factor

The system MUST compute MAR Ratio as `CAGR / max_drawdown`. Recovery Factor as `net_profit / max_drawdown`.

#### Scenario: MAR from CAGR and drawdown

- GIVEN CAGR of 15% and max drawdown of 10%
- WHEN the engine computes MAR Ratio
- THEN the result is 1.5

#### Scenario: Zero drawdown handling

- GIVEN a scenario with zero max drawdown
- WHEN the engine computes MAR or Recovery Factor
- THEN the result is `inf` (positive infinity)

### Requirement: Expectancy

The system MUST compute Expectancy as `avg(win_amount) * win_rate - avg(loss_amount) * loss_rate`. Also SHALL return the Expectancy Ratio (Expectancy / avg(loss_amount)).

#### Scenario: Expectancy from win/loss distribution

- GIVEN 60 winning trades averaging 200 and 40 losing trades averaging 100
- WHEN the engine computes Expectancy
- THEN the result is `200 * 0.6 - 100 * 0.4 = 80.0`

#### Scenario: Empty trade list raises error

- GIVEN an empty trade list
- WHEN the engine attempts to compute any metric
- THEN an InsufficientDataError is raised
