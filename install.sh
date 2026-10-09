#!/usr/bin/env bash
# QuantLab AI — One-command installer
# Usage: curl -sSL https://raw.githubusercontent.com/andrikonbeat/quantlabai/main/install.sh | bash
#        or: bash install.sh [--no-wizard] [--dev] [--skip-tests]

set -euo pipefail

# ──────────────────────────────────────────────────────────────────────
# Config
REPO_URL="https://github.com/andrikonbeat/quantlabai.git"
REPO_DIR="quantlabai"
PYTHON_MIN_VERSION="3.11"
GO_MIN_VERSION="1.23"

# Flags
NO_WIZARD=false
DEV_MODE=false
SKIP_TESTS=false
FORCE_MOCK=true

# ──────────────────────────────────────────────────────────────────────
# Helpers
log()   { printf "\033[1;34m[INFO]\033[0m %s\n" "$*"; }
ok()    { printf "\033[1;32m[OK]\033[0m %s\n" "$*"; }
warn()  { printf "\033[1;33m[WARN]\033[0m %s\n" "$*"; }
err()   { printf "\033[1;31m[ERR]\033[0m %s\n" "$*" >&2; }
die()   { err "$*"; exit 1; }

version_ge() {
    local v1="$1" v2="$2"
    [ "$v1" = "$v2" ] && return 0
    printf '%s\n%s\n' "$v2" "$v1" | sort -V | head -1 | grep -q "^$v2$"
}

check_cmd() {
    command -v "$1" >/dev/null 2>&1
}

# ──────────────────────────────────────────────────────────────────────
# Parse args
for arg in "$@"; do
    case "$arg" in
        --no-wizard)  NO_WIZARD=true ;;
        --dev)        DEV_MODE=true ;;
        --skip-tests) SKIP_TESTS=true ;;
        --no-mock)    FORCE_MOCK=false ;;
        *) die "Unknown flag: $arg (use --no-wizard|--dev|--skip-tests|--no-mock)" ;;
    esac
done

# ──────────────────────────────────────────────────────────────────────
log "QuantLab AI — One-command installer"
log "Repo: $REPO_URL"

# ── 1. Check prerequisites ──────────────────────────────────────────
log "Checking prerequisites..."

# Python
if check_cmd python3; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if version_ge "$PY_VER" "$PYTHON_MIN_VERSION"; then
        ok "Python $PY_VER (>= $PYTHON_MIN_VERSION)"
    else
        die "Python $PY_VER found, but $PYTHON_MIN_VERSION+ required. Install from https://python.org"
    fi
else
    die "python3 not found. Install Python $PYTHON_MIN_VERSION+ from https://python.org"
fi

# pip
if ! check_cmd pip3 && ! python3 -m pip --version >/dev/null 2>&1; then
    warn "pip not found — upgrading via ensurepip"
    python3 -m ensurepip --upgrade >/dev/null 2>&1 || die "Failed to bootstrap pip"
fi

# Git
check_cmd git || die "git not found. Install git first."

# Go (optional, for installer binary)
HAS_GO=false
if check_cmd go; then
    GO_VER=$(go version | awk '{print $3}' | sed 's/^go//')
    if version_ge "$GO_VER" "$GO_MIN_VERSION"; then
        ok "Go $GO_VER (>= $GO_MIN_VERSION) — installer binary will be built"
        HAS_GO=true
    else
        warn "Go $GO_VER found, but $GO_MIN_VERSION+ required for installer binary. Skipping Go installer build."
    fi
else
    warn "Go not found — installer binary will not be built (Python-only install)."
fi

# ──────────────────────────────────────────────────────────────────────
# Detect if we're already inside a valid checkout
# Case 1: run from parent dir, REPO_DIR exists
# Case 2: run from inside repo (current dir has sdk/pyproject.toml)
# Case 3: fresh install, need to clone

if [ -f "sdk/pyproject.toml" ] && [ -f "pytest.ini" ]; then
    # Already inside the repo
    log "Using current directory (already a QuantLab checkout)"
elif [ -d "$REPO_DIR/.git" ]; then
    # Repo exists in subdir, update and enter
    log "Repository exists — updating..."
    cd "$REPO_DIR"
    git fetch origin
    git reset --hard origin/main
elif [ -d "$REPO_DIR" ] && [ -f "$REPO_DIR/sdk/pyproject.toml" ] && [ -f "$REPO_DIR/pytest.ini" ]; then
    # Repo exists but not a git dir (copied), use it
    log "Using existing checkout at $REPO_DIR"
    cd "$REPO_DIR"
else
    # Fresh clone
    log "Cloning repository..."
    git clone --depth 1 "$REPO_URL" "$REPO_DIR"
    cd "$REPO_DIR"
fi

log "Working in $(pwd)"

# ──────────────────────────────────────────────────────────────────────
# Python venv + SDK install
log "Setting up Python virtual environment..."
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

log "Upgrading pip..."
python -m pip install -U pip -q

log "Installing QuantLab SDK [dev]..."
pip install -e "sdk[dev]" -q

ok "Python environment ready"

# ──────────────────────────────────────────────────────────────────────
# Optional: Build Go installer binary
if [ "$HAS_GO" = true ]; then
    log "Building Go installer binary..."
    cd installer
    make build >/dev/null 2>&1
    cd ..
    ok "Installer binary at installer/build/quantlab"
fi

# ──────────────────────────────────────────────────────────────────────
# Run Go installer (optional, runs full onboarding + sync)
if [ "$HAS_GO" = true ] && [ -f installer/build/quantlab ]; then
    log "Running QuantLab installer (full setup: SDK + OpenCode agents + skills + prompts)..."
    INSTALL_ARGS=()
    [ "$NO_WIZARD" = true ] && INSTALL_ARGS+=(--no-wizard)
    ./installer/build/quantlab install "${INSTALL_ARGS[@]}"
    ok "QuantLab installer completed"
else
    log "Skipping Go installer (not built). Python SDK is ready."
    log "To sync OpenCode agents/skills/prompts later, run:"
    log "  python3 ai/opencode/sync_prompts.py"
    log "  python3 ai/opencode/sync_skills.py"
fi

# ──────────────────────────────────────────────────────────────────────
# Sync prompts & skills (idempotent)
log "Syncing agent prompts & skills..."
python3 ai/opencode/sync_prompts.py
python3 ai/opencode/sync_skills.py
ok "Prompts & skills synced to ~/.config/opencode/"

# ──────────────────────────────────────────────────────────────────────
# Verify
if [ "$SKIP_TESTS" = false ]; then
    log "Running verification tests (SQX_FORCE_MOCK=1)..."
    if [ "$FORCE_MOCK" = true ]; then
        export SQX_FORCE_MOCK=1
    fi
    python3 -m pytest -q
    ok "All tests passed"
else
    warn "Tests skipped (--skip-tests)"
fi

# ──────────────────────────────────────────────────────────────────────
# Summary
cat <<EOF

\033[1;32m═══════════════════════════════════════════════════════════════\033[0m
\033[1;32m  QuantLab AI installed successfully!\033[0m
\033[1;32m═══════════════════════════════════════════════════════════════\033[0m

Repository: $(pwd)
Virtualenv: $(pwd)/.venv  (activate with: source .venv/bin/activate)

\033[1mNext steps:\033[0m
  1. Activate env:    \033[0;36msource .venv/bin/activate\033[0m
  2. Configure API:   \033[0;36mcp .env.example .env && \$EDITOR .env\033[0m
     (add OPENCODE_API_KEY for LLM agents, SQX_INSTALL_PATH for real backtests)
  3. Open OpenCode:   \033[0;36mopencode\033[0m  → select agent: \033[1mquantlab-orchestrator\033[0m
  4. Run a campaign:  \033[0;36mquantlab run-campaign\033[0m  (or use the agent)

\033[1mUseful commands:\033[0m
  \033[0;36mquantlab status\033[0m          # verify installation
  \033[0;36mquantlab sync\033[0m            # re-sync agents/skills/prompts
  \033[0;36mSQX_FORCE_MOCK=1 python -m pytest -q\033[0m  # run tests
  \033[0;36mquantlab dashboard\033[0m       # start local dashboard

\033[1mDocumentation:\033[0m
  \033[0;36mdocs/HANDOFF.md\033[0m     — complete setup guide
  \033[0;36mdocs/STATE.md\033[0m      — project status snapshot
  \033[0;36mREADME.md\033[0m          — architecture & quick start

EOF