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

# ── remove legacy files from old install.sh ───────────────────────────────────
# Previous versions created wrapper scripts and compiled binaries here.
for bin in nq nqtail nqterm; do
    wrapper="${HOME}/.local/bin/${bin}"
    if [ -f "${wrapper}" ]; then
        rm -f "${wrapper}"
        ok "removed ${wrapper}"
    fi
done

LIBEXEC_DIR="${HOME}/.local/lib/nqi"
if [ -d "${LIBEXEC_DIR}" ]; then
    rm -rf "${LIBEXEC_DIR}"
    ok "removed legacy ${LIBEXEC_DIR}"
fi

# ── check for NQDIR in shell rc ──────────────────────────────────────────────
case "${SHELL:-}" in
    */zsh)  RC_FILE="${HOME}/.zshrc" ;;
    */bash) RC_FILE="${HOME}/.bashrc" ;;
    *)      RC_FILE="${HOME}/.profile" ;;
esac

if grep -qF 'NQDIR' "${RC_FILE}" 2>/dev/null; then
    warn "Your ${RC_FILE} contains an NQDIR export. You may want to remove it:"
    grep -n 'NQDIR' "${RC_FILE}"
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
