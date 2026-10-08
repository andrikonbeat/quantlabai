#!/usr/bin/env bash
set -euo pipefail

# QuantLab AI - Interactive Installer
# Copy/paste this script in terminal to start guided setup

main() {
  echo "QuantLab AI - Instalador interactivo"
  echo "===================================="
  detect_os
  echo ""
  show_intro
}

detect_os() {
  case "$(uname -s)" in
    Linux*)  echo "SO detectado: Linux ($(uname -m))";;
    Darwin*) echo "SO detectado: macOS ($(uname -m))";;
    MINGW*|MSYS*|CYGWIN*) echo "SO detectado: Windows (WSL recomendado) ($(uname -m))";;
    *)       echo "SO detectado: $(uname -s) ($(uname -m))";;
  esac
}

show_intro() {
  cat <<'EOF'
QuantLab AI es un motor de investigación dirigido por IA que trabaja junto con
StrategyQuant X (motor de cómputo) para generar, evaluar y desplegar estrategias
automatizadas.

Componentes principales:
- OpenCode: capa agéntica que orquesta todo el flujo (requerido)
- gentle-ai: capa de compatibilidad (recomendado/esperado por el ecosistema)
- StrategyQuant X: software de generación/backtest (externo, requiere licencia)
- JForex 4: plataforma de despliegue (externo, cuenta gratuita disponible)

Este instalador te guiará paso a paso para dejar todo listo.
EOF
  read -rp "¿Continuar con la instalación guiada? [s/N]: " ans
  [[ "${ans:-n}" =~ ^[Ss]$ ]] || exit 0
}

main "$@"

show_explain() {
  cat <<'EOF'

QuantLab AI: Orquesta campañas de trading algorítmico. Trabaja sobre OpenCode
(agentes) + StrategyQuant X (generación/backtests) + JForex 4 (despliegue).

Dependencias de terceros:
- StrategyQuant X: software externo. Licencia de pago o prueba gratuita de 30 días.
- JForex 4: plataforma Dukascopy. Cuenta demo/gratuita disponible (14 días típicos).
- OpenCode: capa agéntica (requerida). Se puede instalar automático o manual.
- gentle-ai: capa de compatibilidad (detectada/verificada).

EOF
  read -rp "Continuar? [s/N]: " ans
  [[ "${ans:-n}" =~ ^[Ss]$ ]]
}

opencode_flow() {
  cat <<'EOF'

Instalación de OpenCode (capa agéntica)
----------------------------------------
OpenCode es la capa que orquesta QuantLab AI.

Opciones:
1) Automática - Instalar OpenCode automáticamente (recomendado)
2) Manual - Ver URL oficial y seguir instrucciones
0) Saltar (ya lo tengo instalado)

EOF
  read -rp "Selecciona [1/2/0]: " opt
  case "$opt" in
    1) echo "Se recomienda instalar OpenCode desde su web oficial según SO."; echo "URL: https://opencode.ai/";;
    2) echo "URL oficial: https://opencode.ai/";;
    *) echo "Omitiendo...";;
  esac
}

sqx_flow() {
  cat <<'EOF'

StrategyQuant X
---------------
Necesario para builder/backtest. 
Licencia: de pago o prueba gratuita de 30 días (funciona para evaluar).
Cómo obtener licencia: desde sitio oficial de StrategyQuant.

URL oficial: https://strategyquant.com/
EOF
  read -rp "Continuar? [s/N]: " ans
  [[ "${ans:-n}" =~ ^[Ss]$ ]]
}

jforex_flow() {
  cat <<'EOF'

JForex 4 (Despliegue)
--------------------
Plataforma de trading Dukascopy (integración directa con datos SQX).
Cuenta gratuita/demo: disponible (aprox. 14 días). Permite probar despliegue.

Notas: revisar requisitos en sitio oficial.
URL oficial: https://www.dukascopy.com/
EOF
  read -rp "Continuar? [s/N]: " ans
  [[ "${ans:-n}" =~ ^[Ss]$ ]]
}

verification() {
  cat <<'EOF'

Verificación de componentes
--------------------------
Marcar estado (simulado interactivo):
- [ ] OpenCode instalado y accesible
- [ ] gentle-ai detectado (compatibilidad)
- [ ] StrategyQuant X detectado/ruta válida
- [ ] JForex accesible
- [ ] QuantLab SDK/estado OK

Si algún ítem falta, se recomienda delegar la instalación al agente OpenCode
mediante el prompt indicado en el paso final.
EOF
  read -rp "¿Todo parece correcto? [s/N]: " ans
  [[ "${ans:-n}" =~ ^[Ss]$ ]]
}

final_instructions() {
  local proj="${HOME}/projects/QuantLab"
  mkdir -p "$proj" 2>/dev/null || true
  cat <<EOF

Listo para empezar
------------------
1. Abrir OpenCode en la carpeta de proyecto:
   cd "${proj}"
   opencode

2. Pegar el siguiente prompt en OpenCode:
   "Instala la herramienta QuantLab-AI en mi ordenador y dame la guía de introducción."

3. Cuando esté listo, comienza con:
   "Comienza una campaña para un portafolio de 100USD"

Recomendación: el agente evaluará riesgos concretos (100 USD, M15, SL ajustados,
3 instrumentos con baja correlación: EUR/USD, USD/CHF, AUD/USD) y documentará
cada fase antes de avanzar.
EOF
}

main2() {
  detect_os
  show_intro
  show_explain
  opencode_flow
  sqx_flow
  jforex_flow
  verification
  final_instructions
}

main2 "$@"
