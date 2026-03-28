#!/usr/bin/env bash
# uninstall.sh – Uninstall nqi (TUI) + nq/nqtail/nqterm (C utilities)
#
# Usage:
#   ./uninstall.sh

set -euo pipefail

NQ_DIR="${HOME}/.local/share/nq"

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==> \033[0m%s\n' "$*"; }
ok()    { printf '\033[1;32m ok \033[0m%s\n' "$*"; }
warn()  { printf '\033[1;33mwarn\033[0m %s\n' "$*" >&2; }

# ── uninstall nqi Python package ──────────────────────────────────────────────
info "Uninstalling nqi..."

if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q nqi; then
    pipx uninstall nqi
    ok "nqi removed via pipx"
elif python3 -m pip show nqi >/dev/null 2>&1; then
    python3 -m pip uninstall -y nqi
    ok "nqi removed via pip"
else
    warn "nqi Python package not found, skipping"
fi

# ── optionally remove job directory ───────────────────────────────────────────
if [ -d "${NQ_DIR}" ]; then
    printf '\n%s' "Remove job directory ${NQ_DIR}? [y/N] "
    read -r answer
    if [[ "${answer}" =~ ^[Yy]$ ]]; then
        rm -rf "${NQ_DIR}"
        ok "removed ${NQ_DIR}"
    else
        info "keeping ${NQ_DIR}"
    fi
fi

echo
echo "  nqi has been uninstalled."
