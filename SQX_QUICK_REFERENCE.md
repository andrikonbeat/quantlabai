# SQX Quick Reference — 144 (Producción) vs 145 (Exploración)

## Versión por defecto: **SQX 144 (2953)**

```bash
export SQX_INSTALL_ROOT="/mnt/Projects/05 - Develop/Proyectos/1- Active/quantlab-ai/SQX_144_2953_linux_dev1_20260601"
export SQX_BROWSER_TOKEN="<desde user/settings/settings.xml>"
```

---

## Comandos rápidos

```bash
# Validar spec (sin live)
quantlab sqx validate spec.json --no-verify

# Validar spec + live (requiere SQX 144 corriendo en 5050)
quantlab sqx validate spec.json --url http://127.0.0.1:5050

# Generar .cfx sin validar
quantlab sqx validate spec.json --no-verify --out project.cfx

# Ver spec parseado
quantlab sqx validate spec.json --no-verify | head -20
```

---

## Spec JSON mínimo

```json
{
  "edit": "Builder",
  "tasks": [{
    "task": "Build",
    "base": "forex",
    "engine": "JForex",
    "symbol": "EURUSD_M1_dukas",
    "timeframe": "M15",
    "range": {"from": "2010-01-01", "to": "2024-10-30"},
    "oos_percent": 30,
    "rankings": [{"column": "ProfitFactor", "op": ">=", "value": 1.2, "sample": "oos"}],
    "max_strategies": 100,
    "stop": {"type": "passed-count", "count": 100},
    "cross_checks": {"all": true, "RetestWithHigherPrecision": {"use": true, "precision": 2}},
    "money_management": {"method": "fixed_size", "size": 0.01, "initial_capital": 100, "max_drawdown": 20},
    "trading_options": {"exit_on_friday": true, "friday_exit_time": 74400, "max_trades_per_day": 2, "min_sl": 15, "max_sl": 25, "min_pt": 10, "max_pt": 60},
    "costs": {"spread": 5, "slippage": 1, "min_distance": 0},
    "fitness": "ReturnDDRatio",
    "what_to_build": {"market_sides": "both", "entry_symmetry": true, "exit_symmetry": true, "conditions": [1,3], "exit_conditions": [0,2], "period": [5,100], "shift": [1,2], "sl_required": true, "pt_required": true}
  }]
}
```

---

## Puertos (144)

| Puerto | Servicio | Comando |
|--------|----------|---------|
| **5050** | API CLI (`/call?cmd=`) | `sqcli -project action=list` |
| **8080** | GUI Web + MCP | `http://127.0.0.1:8080/mcp` |

> ⚠️ **Importante**: Usar `127.0.0.1` (no `localhost`) — Steam ocupa `[::1]:8080` (IPv6)

---

## MCP Tools (solo 144)

```bash
# Conectar MCP (requiere 144 corriendo)
claude mcp add sqx --transport http http://127.0.0.1:8080/mcp

# Tools disponibles (6):
# list_projects, list_databanks, list_strategies, get_strategy_stats, run_project, stop_project
```

---

## Python Version Policy

| Versión | Estado |
|---------|--------|
| **3.12** | ✅ Producción (LTS 2028) |
| **3.13** | ✅ Testing |
| **3.14** | ❌ **NO** — Bug compiler (saltos invertidos) |

---

## CI/CD Gate

```yaml
# .github/workflows/validate.yml
jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e ./sdk
      - run: quantlab sqx validate spec.json --url http://127.0.0.1:5050
        env:
          SQX_BROWSER_TOKEN: ${{ secrets.SQX_BROWSER_TOKEN }}
```

---

## Diferencias clave 144 vs 145

| Feature | 144 (Prod) | 145 (Dev) |
|---------|------------|-----------|
| MCP Server | ✅ 6 tools | ❌ Eliminado |
| Validador live | ✅ 8080 | ❌ 404 |
| Asistente IA | ❌ No | ✅ "Q by SQ" |
| Engine Python | No expuesto | `sqx-project` .pyc |
| Spec JSON | Manual | Declarativo nativo |
| Plugins | `ServletMCP` | Asistente interno |

---

## Archivos clave

| Archivo | Qué hace |
|---------|----------|
| `sdk/quantlab/sqx/validator.py` | CLI `quantlab sqx validate` |
| `sdk/quantlab/sqx/builder.py` | Genera .cfx desde spec |
| `sdk/quantlab/sqx/oracle.py` | Validador live (POST /taskmanager/validateProject) |
| `sdk/quantlab/sqx/builder.py` | Ediciones quirúrgicas XML |
| `sdk/quantlab/sqx/sections.py` | Cross-checks, MM, trading options emitters |
| `sdk/quantlab/sqx/spec.py` | Parser/validator estricto |
| `sdk/quantlab/sqx/templates.py` | Loader defaults XML |
| `sdk/quantlab/sqx/paths.py` | Resuelve install root, puertos |
| `sdk/quantlab/cli/sq_commands.py` | Subcomando `sqx validate` |

---

## Bug Python 3.14 ⚠️

**No usar Python 3.14** — Bug compiler: saltos condicionales invertidos
- `POP_JUMP_IF_NOT_NONE` salta cuando **NO** es None
- `POP_JUMP_IF_FALSE` salta cuando **NO** es False
- Afecta: `parse_stop()` en `sections.py`

**Workaround**: Usar Python ≤3.13 para validación live.

---

## Próximos pasos

1. ✅ Gate CI/CD: `quantlab sqx validate` en CI
2. ⏳ Python 3.12 en CI/CD (15 min)
3. 📋 Issue a Python: compiler bug 3.14 (saltos invertidos)
4. 🔧 Completar `apply_inplace` HTTP si se necesita edición en caliente
