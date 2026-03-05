#!/usr/bin/env bash
# uninstall.sh – Uninstall nqx (TUI) + nq/nqtail/nqterm (C utilities)
#
# Usage:
#   ./uninstall.sh

set -euo pipefail

NQ_DIR="${HOME}/.local/share/nq"
BIN_DIR="${HOME}/.local/bin"

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==> \033[0m%s\n' "$*"; }
ok()    { printf '\033[1;32m ok \033[0m%s\n' "$*"; }
warn()  { printf '\033[1;33mwarn\033[0m %s\n' "$*" >&2; }

# ── uninstall nqx Python package ──────────────────────────────────────────────
info "Uninstalling nqx..."

if command -v pipx >/dev/null 2>&1 && pipx list 2>/dev/null | grep -q nqx-tui; then
    pipx uninstall nqx-tui
    ok "nqx removed via pipx"
elif python3 -m pip show nqx-tui >/dev/null 2>&1; then
    python3 -m pip uninstall -y nqx-tui
    ok "nqx removed via pip"
else
    warn "nqx Python package not found, skipping"
fi

# ── remove nq C utilities ─────────────────────────────────────────────────────
info "Removing nq C utilities..."
for bin in nq nqtail nqterm; do
    if [ -f "${BIN_DIR}/${bin}" ]; then
        rm "${BIN_DIR}/${bin}"
        ok "removed ${BIN_DIR}/${bin}"
    else
        warn "${BIN_DIR}/${bin} not found, skipping"
    fi
done

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
echo "  nqx has been uninstalled."
