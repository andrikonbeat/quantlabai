# QuantLabBridge — JSON Command Protocol

## Overview
Stateless Java subprocess bridge. One command per invocation. JSON request on stdin, JSON response on stdout. Exit code 0 = success, non-zero = error (stderr has details).

## Common Types

```json
// Success response
{"ok": true, "data": {...}}

// Error response
{"ok": false, "error": "HUMAN_READABLE_MESSAGE", "code": "ERROR_CODE", "details": {...}}
```

Error codes: `CONNECTION_FAILED`, `AUTH_FAILED`, `STRATEGY_NOT_FOUND`, `COMPILATION_FAILED`, `DEPLOY_FAILED`, `ALREADY_RUNNING`, `NOT_RUNNING`, `INVALID_ARGUMENT`, `SDK_ERROR`, `IO_ERROR`

## Commands

### 1. `connect` — Establish JForex session
**Request:**
```json
{
  "cmd": "connect",
  "jnlp_url": "http://platform.dukascopy.com/demo/jforex.jnlp",
  "username": "demo_user",
  "password": "demo_pass",
  "pin": "optional_pin_for_live",
  "mode": "demo|live"
}
```
**Response:**
```json
{"ok": true, "data": {"connected": true, "account_id": "DEMO_12345", "server_time": 1699999999999}}
```

### 2. `compile` — Compile .java → .jfx
**Request:**
```json
{
  "cmd": "compile",
  "source_path": "/path/to/MyStrategy.java",
  "output_path": "/path/to/MyStrategy.jfx",
  "classpath": ["/extra/jars/*.jar"]
}
```
**Response:**
```json
{"ok": true, "data": {"jfx_path": "/path/to/MyStrategy.jfx", "warnings": []}}
```

### 3. `deploy` — Copy .jfx to JForex strategies directory
**Request:**
```json
{
  "cmd": "deploy",
  "jfx_path": "/path/to/MyStrategy.jfx",
  "strategy_name": "MyStrategy",
  "jforex_home": "/home/user/JForex4"
}
```
**Response:**
```json
{"ok": true, "data": {"deployed_path": "/home/user/JForex4/Strategies/MyStrategy.jfx"}}
```

### 4. `start` — Start strategy (local or remote)
**Request:**
```json
{
  "cmd": "start",
  "strategy_name": "MyStrategy",
  "mode": "local|remote",
  "jforex_home": "/home/user/JForex4",
  "parameters": {"instrument": "EUR/USD", "lot_size": 0.1}
}
```
**Response:**
```json
{"ok": true, "data": {"strategy_id": 123456789, "running": true}}
```

### 5. `stop` — Stop running strategy
**Request:**
```json
{
  "cmd": "stop",
  "strategy_id": 123456789
}
```
**Response:**
```json
{"ok": true, "data": {"stopped": true}}
```

### 6. `status` — Get connection and strategy status
**Request:**
```json
{"cmd": "status"}
```
**Response:**
```json
{
  "ok": true,
  "data": {
    "connected": true,
    "account_id": "DEMO_12345",
    "equity": 10050.25,
    "balance": 10000.00,
    "strategies": [
      {"id": 123456789, "name": "MyStrategy", "running": true, "start_time": 1699990000000}
    ]
  }
}
```

### 7. `account` — Get detailed account info
**Request:**
```json
{"cmd": "account"}
```
**Response:**
```json
{
  "ok": true,
  "data": {
    "account_id": "DEMO_12345",
    "equity": 10050.25,
    "balance": 10000.00,
    "used_margin": 500.00,
    "free_margin": 9550.25,
    "profit_loss": 50.25,
    "margin_level": 2010.05,
    "leverage": 100,
    "currency": "USD"
  }
}
```

### 8. `disconnect` — Clean disconnect
**Request:**
```json
{"cmd": "disconnect"}
```
**Response:**
```json
{"ok": true, "data": {"disconnected": true}}
```

## Session Management
- Bridge is **stateless** — each command creates own `IClient`, connects, executes, disconnects
- For multi-command workflows (connect → compile → deploy → start), Python layer manages sequence
- Reconnection logic lives in Python (`JForexStrategyBridge`), not in bridge

## Configuration
Bridge reads config from:
1. `--config /path/to/config.json` (optional)
2. Environment variables: `JFOREX_JNLP_URL`, `JFOREX_USER`, `JFOREX_PASS`, `JFOREX_PIN`, `JFOREX_HOME`
3. Defaults: demo JNLP, no credentials

## Build
```bash
cd bridge/java
mvn clean package -DskipTests
# Output: target/quantlab-bridge-1.0.0-fat.jar
```

## Usage from Python
```python
import subprocess, json

def bridge_cmd(cmd: dict) -> dict:
    result = subprocess.run(
        ["java", "-cp", "bridge.jar", "com.quantlab.jforex.QuantLabBridge"],
        input=json.dumps(cmd).encode(),
        capture_output=True,
        timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"Bridge failed: {result.stderr.decode()}")
    return json.loads(result.stdout)
```