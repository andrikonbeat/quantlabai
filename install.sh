#!/usr/bin/env bash
# QuantLab AI — One-command installer
#
# GUIADA (TUI, recomendada — te deja dentro de la guía de instalación):
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh)"
#
# AUTONOMA (sin wizard, para CI o instalación desatendida):
#   curl -sSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh | bash -s -- --no-wizard
#
# Local: bash install.sh [--no-wizard|--yes] [--onboarding|--no-onboarding] [--force] [--dev] [--skip-tests]

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────
# Config
REPO_URL="https://github.com/andrikonbeat/quantlabai.git"
REPO_SSH="git@github.com:andrikonbeat/quantlabai.git"
REPO_DIR="quantlabai"
PYTHON_MIN_VERSION="3.11"
GO_MIN_VERSION="1.23"
MIN_FREE_MB=2048
TOTAL_STEPS=7
STEP=0
START_TIME=$SECONDS

# Flags
NO_WIZARD=false
FORCE=false
RUN_ONBOARDING="auto"
DEV_MODE=false
SKIP_TESTS=false
FORCE_MOCK=true

# Estado interno (para limpieza segura ante cortes)
CLONING=false
CLONE_CREATED=false

# ──────────────────────────────────────────────────────────────────────
# Helpers de presentación
log()   { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m  ✓ %s\033[0m\n" "$*"; }
warn()  { printf "\033[1;33m  ⚠ %s\033[0m\n" "$*" >&2; }
err()   { printf "\033[1;31m  ✗ %s\033[0m\n" "$*" >&2; }
die()   { err "$*"; exit 1; }
step()  {
    STEP=$((STEP + 1))
    printf "\n\033[1;36m━━━━━━━━━━━ [%d/%d] %s ━━━━━━━━━━━\033[0m\n" "$STEP" "$TOTAL_STEPS" "$1"
}
banner() {
    printf "\033[1;32m"
    cat <<'BANNER'
   ____                    _   _          _          _    ___
  / __ \_   _  __ _ _ __ | |_| |    __ _| |__      / \  |_ _|
 | |  | | | | |/ _` | '_ \| __| |   / _` | '_ \   / _ \  | |
 | |_| | |_| | (_| | | | | |_| |__| (_| | |_) | / ___ \ | |
  \__\_\\__,_|\__,_|_| |_|\__|_____\__,_|_.__/ /_/   \_\___|
BANNER
    printf "\033[0m  One-command installer · prepara todo y te deja en la guía TUI\n\n"
}

version_ge() {
    local v1="$1" v2="$2"
    [ "$v1" = "$v2" ] && return 0
    printf '%s\n%s\n' "$v2" "$v1" | sort -V | head -1 | grep -q "^$v2$"
}

check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

elapsed() {
    local s=$((SECONDS - START_TIME))
    printf "%dm%02ds" $((s / 60)) $((s % 60))
}

# ──────────────────────────────────────────────────────────────────────
# Parse args
for arg in "$@"; do
    case "$arg" in
        --no-wizard|--skip-wizard|--yes) NO_WIZARD=true ;;
        --onboarding)    RUN_ONBOARDING=true ;;
        --no-onboarding) RUN_ONBOARDING=false ;;
        --force)         FORCE=true ;;
        --dev)           DEV_MODE=true ;;
        --skip-tests)    SKIP_TESTS=true ;;
        --no-mock)       FORCE_MOCK=false ;;
        *) die "Unknown flag: $arg (use --no-wizard|--yes|--onboarding|--no-onboarding|--force|--dev|--skip-tests|--no-mock)" ;;
    esac
done

# Si la entrada viene de un pipe (curl | bash) no hay TTY para el wizard.
if [ "$NO_WIZARD" = false ] && [ ! -t 0 ] && [ ! -c /dev/tty ]; then
    warn "Sin terminal interactiva (entrada por pipe) — el wizard TUI se salteará."
    warn "Para la guía TUI usá: bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh)\""
fi

banner
log "Repo: $REPO_URL"

# ──────────────────────────────────────────────────────────────────────
# Protección: nunca borrar a ciegas. Si un directorio existe pero no es un
# checkout válido y no lo creamos nosotros en esta corrida, se mueve a un
# backup con fecha en vez de eliminarse. Solo los clones parciales propios
# (fallidos en el loop de abajo) se borran directo.
quarantine_dir() {
    local dir="$1" reason="$2"
    local backup="${dir}.corrupto-$(date +%Y%m%d-%H%M%S)"
    warn "$reason"
    warn "Moviendo '$dir' a '$backup' (no se borra nada tuyo)."
    mv "$dir" "$backup"
}

# Limpieza ante corte (Ctrl+C, caída de red, error): si estábamos clonando y
# el directorio lo creamos nosotros, se elimina el parcial para no dejar
# un checkout corrupto. No toca nada preexistente del usuario.
cleanup_partial() {
    if [ "$CLONING" = true ] && [ "$CLONE_CREATED" = true ] && [ -d "$REPO_DIR" ]; then
        if [ ! -f "$REPO_DIR/sdk/pyproject.toml" ]; then
            warn "Clon interrumpido — limpiando parcial en '$REPO_DIR/'..."
            rm -rf "$REPO_DIR"
        fi
    fi
}
trap cleanup_partial EXIT INT TERM

# Un checkout es válido si git lo reconoce y tiene los marcadores del proyecto.
verify_checkout() {
    local dir="$1"
    [ -d "$dir/.git" ] || return 1
    git -C "$dir" rev-parse --git-dir >/dev/null 2>&1 || return 1
    [ -f "$dir/sdk/pyproject.toml" ] && [ -f "$dir/pytest.ini" ] && [ -f "$dir/install.sh" ]
}

# ──────────────────────────────────────────────────────────────────────
step "Prerrequisitos"
[ "$(id -u)" = "0" ] && warn "Corriendo como root — se recomienda un usuario normal."

# Python
if check_cmd python3; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if version_ge "$PY_VER" "$PYTHON_MIN_VERSION"; then
        ok "Python $PY_VER (>= $PYTHON_MIN_VERSION)"
    else
        die "Python $PY_VER encontrado, pero se requiere $PYTHON_MIN_VERSION+. Descargalo en https://python.org"
    fi
else
    die "python3 no encontrado. Instalá Python $PYTHON_MIN_VERSION+ desde https://python.org"
fi

# pip
if ! check_cmd pip3 && ! python3 -m pip --version >/dev/null 2>&1; then
    warn "pip no encontrado — intentando ensurepip"
    python3 -m ensurepip --upgrade >/dev/null 2>&1 || die "No se pudo iniciar pip"
fi

# Git
check_cmd git || die "git no encontrado. Instalalo primero."

# Espacio libre (el repo + venv pesan ~1 GB)
if check_cmd df; then
    FREE_KB=$(df -k . 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "$FREE_KB" ] && [ "$FREE_KB" -lt $((MIN_FREE_MB * 1024)) ]; then
        die "Poco espacio libre (${FREE_KB} KB). Liberá al menos $MIN_FREE_MB MB."
    fi
fi

# Go (opcional, para el binario instalador)
HAS_GO=false
if check_cmd go; then
    GO_VER=$(go version | awk '{print $3}' | sed 's/^go//')
    if version_ge "$GO_VER" "$GO_MIN_VERSION"; then
        ok "Go $GO_VER (>= $GO_MIN_VERSION) — se compilará el instalador TUI"
        HAS_GO=true
    else
        warn "Go $GO_VER encontrado, pero se pide $GO_MIN_VERSION+ para el binario. Instalación solo-Python."
    fi
else
    warn "Go no encontrado — instalación solo-Python (sin binario TUI)."
fi

# Red: chequeo rápido antes del clon pesado (falla rápido con mensaje claro).
if [ ! -f "sdk/pyproject.toml" ] && [ ! -d "$REPO_DIR/.git" ]; then
    log "Probando conexión con GitHub..."
    if ! git ls-remote "$REPO_URL" HEAD >/dev/null 2>&1; then
        die "No se puede contactar $REPO_URL. Revisá tu conexión o probá por SSH: git clone $REPO_SSH"
    fi
    ok "GitHub alcanzable"
fi

# ──────────────────────────────────────────────────────────────────────
step "Repositorio"

if [ -f "sdk/pyproject.toml" ] && [ -f "pytest.ini" ]; then
    log "Ya estás dentro de un checkout válido — lo uso."
elif [ -d "$REPO_DIR/.git" ]; then
    if verify_checkout "$REPO_DIR"; then
        log "Existe $REPO_DIR/ — actualizando a origin/main..."
        git -C "$REPO_DIR" fetch origin
        git -C "$REPO_DIR" reset --hard origin/main
        cd "$REPO_DIR"
    else
        quarantine_dir "$REPO_DIR" "Existe '$REPO_DIR/' pero el .git está roto."
        log "Clonando de cero..."
        CLONING=true
        git clone --depth 1 "$REPO_URL" "$REPO_DIR"
        CLONING=false
        verify_checkout "$REPO_DIR" || die "El clon quedó inválido. Revisá disco/red e intentá de nuevo."
        cd "$REPO_DIR"
    fi
elif [ -d "$REPO_DIR" ]; then
    # Existe pero sin .git: ¿copia válida o resto corrupto?
    if [ -f "$REPO_DIR/sdk/pyproject.toml" ] && [ -f "$REPO_DIR/pytest.ini" ]; then
        log "Existe $REPO_DIR/ (copia sin .git pero válida) — lo uso."
        cd "$REPO_DIR"
    elif [ "$FORCE" = true ]; then
        quarantine_dir "$REPO_DIR" "Existe '$REPO_DIR/' irreconocible y pasaste --force."
        CLONING=true; CLONE_CREATED=false
        git clone --depth 1 "$REPO_URL" "$REPO_DIR"
        CLONING=false
        verify_checkout "$REPO_DIR" || die "El clon quedó inválido."
        cd "$REPO_DIR"
    else
        die "Existe '$REPO_DIR/' pero no es un checkout válido (¿clon cortado?). Pasá --force para moverlo a backup y clonar de cero, o borralo/movelo a mano."
    fi
else
    # Clon fresco con reintentos (la red a veces corta el pack a mitad).
    # Cada intento parte de cero y solo borra el parcial que creó este script.
    log "Clonando repositorio (shallow, --depth 1)..."
    CLONING=true
    cloned=false
    for attempt in 1 2 3; do
        rm -rf "$REPO_DIR"
        CLONE_CREATED=true
        if GIT_HTTP_VERSION=HTTP/1.1 git clone --depth 1 "$REPO_URL" "$REPO_DIR"; then
            if verify_checkout "$REPO_DIR"; then
                cloned=true
                break
            fi
            warn "El clon terminó pero el checkout no verifica (intento $attempt/3)."
        else
            warn "Clone falló (intento $attempt/3) — reintentando en 5s..."
        fi
        sleep 5
    done
    CLONING=false
    CLONE_CREATED=false
    [ "$cloned" = true ] || die "No se pudo clonar $REPO_URL tras 3 intentos. Revisá tu conexión o probá por SSH: git clone $REPO_SSH"
    cd "$REPO_DIR"
fi

verify_checkout "." || die "El checkout en '$(pwd)' no verifica. Abortando antes de tocar nada."
ok "Checkout válido en $(pwd)"

# ──────────────────────────────────────────────────────────────────────
step "Entorno Python"
if [ -x ".venv/bin/python" ]; then
    log "Reutilizando .venv existente..."
else
    log "Creando .venv..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

log "Actualizando pip..."
python -m pip install -U pip -q

log "Instalando QuantLab SDK [dev]..."
pip install -e "sdk[dev]" -q

ok "Entorno Python listo"

# ──────────────────────────────────────────────────────────────────────
step "Binario instalador (TUI)"
if [ "$HAS_GO" = true ]; then
    log "Compilando instalador Go..."
    (cd installer && make build >/dev/null 2>&1)
    ok "Binario en installer/build/quantlab"
else
    warn "Sin Go — se salta el binario TUI (queda el SDK Python)."
fi

# ──────────────────────────────────────────────────────────────────────
# TUI: el binario decide solo si abre el wizard (terminal + sin --no-wizard).
# Como install.sh puede venir pipeado, reabrimos /dev/tty para darle teclado.
step "Instalador TUI + guía"
run_quantlab_tui() {
    # $1 = subcomando (install u onboarding), resto = args
    local sub="$1"; shift
    if [ ! -t 0 ] && [ -c /dev/tty ]; then
        ./installer/build/quantlab "$sub" "$@" < /dev/tty || ./installer/build/quantlab "$sub" "$@"
    else
        ./installer/build/quantlab "$sub" "$@"
    fi
}

if [ "$HAS_GO" = true ] && [ -f installer/build/quantlab ]; then
    log "Ejecutando 'quantlab install' (SDK en ~/.quantlab + agentes/skills/prompts + state)..."
    INSTALL_ARGS=()
    [ "$NO_WIZARD" = true ] && INSTALL_ARGS+=(--no-wizard)
    run_quantlab_tui install "${INSTALL_ARGS[@]}"
    ok "quantlab install completo"
    # Guía post-instalación: manual por defecto si hay terminal.
    if [ "$RUN_ONBOARDING" = "auto" ]; then
        if [ "$NO_WIZARD" = true ]; then
            RUN_ONBOARDING=false
        elif [ -t 0 ] || [ -c /dev/tty ]; then
            RUN_ONBOARDING=true
        else
            RUN_ONBOARDING=false
        fi
    fi
    if [ "$RUN_ONBOARDING" = true ]; then
        log "Abriendo la guía TUI (onboarding)..."
        run_quantlab_tui onboarding || warn "Onboarding cancelado — retomalo con: ./installer/build/quantlab onboarding"
    fi
else
    warn "Binario no disponible — solo SDK Python."
    log "Para agentes/skills/prompts corrés después:"
    log "  python3 ai/opencode/sync_prompts.py"
    log "  python3 ai/opencode/sync_skills.py"
fi

# ──────────────────────────────────────────────────────────────────────
step "Sincronización repo → live"
log "Sincronizando prompts y skills (el repo manda)..."
python3 ai/opencode/sync_prompts.py
python3 ai/opencode/sync_skills.py
ok "Prompts y skills en ~/.config/opencode/"

# ──────────────────────────────────────────────────────────────────────
step "Verificación"
if [ "$SKIP_TESTS" = false ]; then
    log "Corriendo suite de verificación (SQX_FORCE_MOCK=1)..."
    if [ "$FORCE_MOCK" = true ]; then
        export SQX_FORCE_MOCK=1
    fi
    python3 -m pytest -q
    ok "Tests en verde"
else
    warn "Tests salteados (--skip-tests)"
fi

# ──────────────────────────────────────────────────────────────────────
# Resumen
cat <<EOF

\033[1;32m═══════════════════════════════════════════════════════════════\033[0m
\033[1;32m  QuantLab AI instalado en $(elapsed) ✓\033[0m
\033[1;32m═══════════════════════════════════════════════════════════════\033[0m

Repositorio: $(pwd)
Venv dev:    $(pwd)/.venv  (activar: source .venv/bin/activate)
Venv prod:   ~/.quantlab/venv
Estado:      ~/.quantlab/state.json

\033[1mPróximos pasos:\033[0m
  1. Activar:      \033[0;36msource .venv/bin/activate\033[0m
  2. Configurar:   \033[0;36mcp .env.example .env && \$EDITOR .env\033[0m
     (OPENCODE_API_KEY para agentes LLM, SQX_INSTALL_PATH para backtests reales)
  3. Abrir OpenCode: \033[0;36mopencode\033[0m → agente \033[1mquantlab-orchestrator\033[0m

\033[1mComandos útiles:\033[0m
  \033[0;36mquantlab status\033[0m     verificar instalación
  \033[0;36mquantlab sync\033[0m       re-sincronizar agentes/skills/prompts
  \033[0;36mquantlab onboarding\033[0m reabrir la guía TUI
  \033[0;36mquantlab dashboard\033[0m  dashboard local

\033[1mDocs:\033[0m docs/HANDOFF.md · docs/STATE.md · README.md
EOF
