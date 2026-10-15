# SQX Version Policy

## Default Version: **SQX 144 (2953)** — Estable / Producción

### Justificación
- **MCP Server operativo**: Expone 6 tools vía streamable HTTP en puerto 8080 (`/mcp`)
- **Validador live funcional**: Endpoint `taskmanager/validateProject` responde en puerto 8080
- **Versión estable**: Build 2953 (junio 2026), usada en producción
- **MCP Server funcional**: 6 tools (`list_projects`, `list_databanks`, `list_strategies`, `get_strategy_stats`, `run_project`, `stop_project`)
- **Arquitectura probada**: Usada en producción real

### SQX 145 (3191, dev, oct-2026) — Solo exploración
- **MCP Server**: Eliminado (plugin `ServletMCP` removido)
- **Validador live**: Endpoint `taskmanager/validateProject` **no existe** (404)
- **Asistente IA**: "Q by StrategyQuant" con engine Python propio (`sqx-project` .pyc)
- **Arquitectura nueva**: Asistente interno con spec JSON declarativo + engine Python (`sqx-project` .pyc)
- **Uso recomendado**: Solo exploración/arquitectura, **no producción**

---

## Configuración por defecto

### Para producción (quantlab-ai)
```bash
# En .env o variables de entorno
SQX_INSTALL_ROOT=/mnt/Projects/05 - Develop/Proyectos/1- Active/quantlab-ai/SQX_144_2953_linux_dev1_20260601
SQX_WEB_PORT=8080
SQX_API_PORT=5050
SQX_BROWSER_TOKEN=<desde user/settings/settings.xml tras primer run>
```

### Variables de entorno requeridas
```bash
export SQX_INSTALL_ROOT="/mnt/Projects/05 - Develop/Proyectos/1- Active/quantlab-ai/SQX_144_2953_linux_dev1_20260601"
export SQX_BROWSER_TOKEN="<del settings.xml tras primer run>"
export SQX_FORCE_MOCK=1  # solo para tests sin SQX real
```

---

## Configuración de puertos (144)

| Puerto | Servicio | Uso |
|--------|----------|-----|
| **8080** | GUI Web + MCP Server | MCP streamable HTTP (`/mcp`), GUI web, validador live |
| **5050** | API CLI (`/call?cmd=`) | sqcli HTTP API, comandos CLI |

> **Nota**: 144 usa puerto 8080 para GUI+MCP (145 usa 8081). Steam ocupa `[::1]:8080` (IPv6) → usar `127.0.0.1:8080` explícito.

---

## Validación live (solo 144)

```bash
# Generar .cfx y validar
quantlab sqx validate spec.json --url http://127.0.0.1:5050

# Output esperado:
# VALIDATE PASS
# VALIDATE_JSON {"success":true,"verdict":"PASS","warning":"differs from this build (144.2953)"}
```

### MCP Tools disponibles (144)
| Tool | Params | Descripción |
|------|--------|-------------|
| `list_projects` | — | Lista proyectos |
| `list_databanks` | `name` (project) | Databanks de un proyecto |
| `list_strategies` | `name`, `databank` | Estrategias en databank |
| `get_strategy_stats` | `name`, `databank`, `strategy` | Stats de una estrategia |
| `run_project` | `name` | Arranca proyecto |
| `stop_project` | `name` | Para proyecto |

---

## Configuración de CI/CD (recomendada)

```yaml
# .github/workflows/validate.yml
jobs:
  validate-sqx:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"  # NO 3.14 (bug compiler)
      
      - name: Install quantlab
        run: pip install -e ./sdk
      
      - name: Validate SQX spec
        run: |
          quantlab sqx validate spec.json \
            --url http://127.0.0.1:5050
        env:
          SQX_BROWSER_TOKEN: ${{ secrets.SQX_BROWSER_TOKEN }}
          SQX_INSTALL_ROOT: /opt/sqx-144
```

---

## Python Version Policy

| Python | Estado | Uso |
|--------|--------|-----|
| **3.12** | ✅ Recomendado | Producción, CI/CD (LTS hasta 2028) |
| **3.13** | ✅ OK | Testing, compatible |
| **3.14** | ❌ **NO USAR** | Bug compiler: saltos condicionales invertidos |

### Bug Python 3.14 documentado
- **Issue**: Saltos condicionales invertidos (`POP_JUMP_IF_NOT_NONE`, `POP_JUMP_IF_FALSE`, `POP_JUMP_IF_TRUE`)
- **Afecta**: `parse_stop()` en `sections.py` - no lanza `ValueError` en dict vacío
- **Workaround**: Usar Python ≤3.13 para validación live
- **Reporte**: Pendiente en github.com/python/cpython/issues

---

## Arquitectura de referencia (144 vs 145)

| Componente | 144 (Producción) | 145 (Exploración) |
|------------|------------------|-------------------|
| MCP Server | ✅ 6 tools, HTTP 8080 | ❌ Eliminado |
| Validador live | ✅ `/taskmanager/validateProject` | ❌ 404 |
| Asistente IA | ❌ No existe | ✅ "Q by StrategyQuant" |
| Engine Python | ❌ No expuesto | ✅ `sqx-project` .pyc (7 módulos) |
| Spec JSON | Manual | Declarativo nativo |
| Validación live | Side-effect-free | N/A |
| Plugins | `ServletMCP` | Asistente interno |

---

## Checklist de puesta en producción

- [ ] `SQX_INSTALL_ROOT` apunta a 144
- [ ] Puerto 8080 libre (no Steam en IPv6)
- [ ] `SQX_BROWSER_TOKEN` configurado (tras primer run)
- [ ] Python 3.12 en CI/CD
- [ ] `quantlab sqx validate` en CI gate
- [ ] Documentar spec JSON schema para el equipo

---

## Python 3.14 Compiler Bug — Fix Applied

### Bug
Python 3.14.7 compiler inverts conditional jumps:
- `POP_JUMP_IF_NOT_NONE` → salta cuando **NO es** None (debería saltar cuando ES None)
- `POP_JUMP_IF_FALSE` → salta cuando **NO es** False (debería saltar cuando ES False)
- `POP_JUMP_IF_TRUE` → salta cuando **NO es** True (debería saltar cuando ES True)

### Workaround aplicado en `sdk/quantlab/sqx/sections.py`

```python
def parse_stop(stop_dict: dict) -> dict:
    if stop_dict is None:
        return {}
    if len(stop_dict) == 0:
        return {}
    # Use .get() with sentinel to avoid KeyError handling bug
    _MISSING = object()
    type_val = stop_dict.get("type", _MISSING)
    if type_val is _MISSING:
        raise ValueError("Stop section missing 'type'")
    return dict(stop_dict)
```

### Validación en validator.py

```python
# Fail fast on Python 3.14
import sys
if sys.version_info[:2] == (3, 14):
    return ValidationResult(
        ok=False,
        verdict="FAIL",
        validate_json={"error": "Python 3.14 not supported: compiler bug inverts conditional jumps"},
        exit_code=1,
    )
```

### CI/CD Check

```yaml
- name: Check Python version
  run: |
    python -c "import sys; assert sys.version_info[:2] <= (3, 13), f'Python 3.14+ not supported: {sys.version}'"
```

### Versiones soportadas

| Python | Estado | Notas |
|--------|--------|-------|
| 3.11 | ✅ | EOL Oct 2027 |
| 3.12 | ✅ Recomendado | LTS hasta 2028 |
| 3.13 | ✅ | OK |
| 3.14 | ❌ **NO** | Bug compiler |

---

### Verificación rápida

```bash
# Verificar versión
python -c "import sys; assert sys.version_info[:2] <= (3, 13), f'Python 3.14+ no soportado: {sys.version}'"

# Test parse_stop
python -c "from quantlab.sqx.sections import parse_stop; parse_stop({})"  # Debe fallar con ValueError
```
