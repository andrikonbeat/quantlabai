# JForex Strategy Templates for QuantLab

This directory contains Java strategy templates that work with QuantLab's JForex bridge.

## QuantLabTemplateStrategy.java

A fully instrumented strategy that exports state files for QuantLab's monitoring components:

| File | Purpose | Consumed By |
|------|---------|-------------|
| `equity.json` | Equity curve history `[{timestamp, equity}]` | `JForexLiveFeed` |
| `orders.json` | Order history with fills/P&L | `JForexLiveFeed`, `ExecutionGuardian` |
| `health.txt` | Health score 0.0-1.0 | `JForexBrokerAdapter.get_health_score()` |
| `latency.txt` | Latency in milliseconds | `JForexBrokerAdapter.get_latency()` |
| `slippage.txt` | Average slippage in basis points | `JForexBrokerAdapter.get_recent_slippage()` |
| `connection.json` | Connection status + server time | `JForexBrokerAdapter.is_connected()` |

## Usage

### 1. Compile with QuantLabBridge
```bash
# From project root
cd bridge/java
mvn clean package -DskipTests

# Compile strategy
java -cp ../target/quantlab-bridge-1.0.0-fat.jar com.quantlab.jforex.QuantLabBridge <<'EOF'
{
  "cmd": "compile",
  "source_path": "../../strategies/jforex-templates/QuantLabTemplateStrategy.java",
  "output_path": "../../strategies/jforex-templates/QuantLabTemplateStrategy.jfx"
}
EOF
```

### 2. Deploy to JForex
```bash
java -cp ../target/quantlab-bridge-1.0.0-fat.jar com.quantlab.jforex.QuantLabBridge <<'EOF'
{
  "cmd": "deploy",
  "jfx_path": "../../strategies/jforex-templates/QuantLabTemplateStrategy.jfx",
  "strategy_name": "QuantLabTemplateStrategy",
  "jforex_home": "/home/user/JForex4"
}
EOF
```

### 3. Start via QuantLab Python SDK
```python
from quantlab.jforex import JForexStrategyBridge

bridge = JForexStrategyBridge(
    bridge_jar="bridge/java/target/quantlab-bridge-1.0.0-fat.jar",
    jforex_home="/home/user/JForex4"
)

strategy_id = bridge.start("QuantLabTemplateStrategy")
print(f"Started strategy {strategy_id}")

# Monitor via LiveFeed
from quantlab.jforex import JForexLiveFeed
feed = JForexLiveFeed(state_dir=Path("~/JForex4/state").expanduser())
for equity_point in feed.stream_equity():
    print(f"Equity: {equity_point.equity}")
```

### 4. Strategy Parameters
Pass parameters via bridge start command:
```json
{
  "cmd": "start",
  "strategy_name": "QuantLabTemplateStrategy",
  "mode": "remote",
  "jforex_home": "/home/user/JForex4",
  "parameters": {
    "instrument": "EUR/USD",
    "lot_size": 0.1,
    "max_positions": 1,
    "write_interval_ms": 5000,
    "state_dir": "/home/user/JForex4/state"
  }
}
```

## Customizing the Template

1. Copy `QuantLabTemplateStrategy.java` to your strategy name
2. Implement your trading logic in `onBar()` or `onTick()`
3. Keep the state export methods (`writeEquityJson()`, etc.) unchanged
4. Compile and deploy as above

## Requirements

- Java 11+
- JForex SDK (API 2.13.99, DDS2 3.6.51) - bundled in bridge fat-jar
- JForex 4 Desktop installed (for `jforex_home` deploy target)
- Dukascopy demo or live account