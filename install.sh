#!/usr/bin/env bash
# install.sh – Install nqx (TUI) + nq/nqtail/nqterm (C utilities)
#
# Usage:
#   ./install.sh

set -euo pipefail

NQ_DIR="${HOME}/.local/share/nq"

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==> \033[0m%s\n' "$*"; }
ok()    { printf '\033[1;32m ok \033[0m%s\n' "$*"; }
die()   { printf '\033[1;31merr \033[0m%s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || die "Required tool not found: $1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ── pre-flight checks ──────────────────────────────────────────────────────────
# We need make/gcc for the C extension build that happens during pip install
require make
require python3
# Check for a C compiler
if ! command -v gcc >/dev/null 2>&1 && ! command -v clang >/dev/null 2>&1; then
    die "No C compiler found (gcc or clang is required to build nq)."
fi

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" \
    || die "Python 3.8 or newer is required."

# ── install nqx (and build nq automatically) ───────────────────────────────────
info "Installing nqx..."

if command -v pipx >/dev/null 2>&1; then
    # pipx is preferred for application isolation
    pipx install --force "${SCRIPT_DIR}"
    ok "nqx installed via pipx"
else
    # Fallback to pip --user
    python3 -m pip install --user "${SCRIPT_DIR}"
    ok "nqx installed via pip --user"
fi

# ── install nq C utilities ─────────────────────────────────────────────────────
# We explicitly install these to ~/.local/bin because pipx only symlinks
# declared entry points, and nq/nqtail/nqterm are C binaries.
info "Installing nq C utilities..."
make -C "${SCRIPT_DIR}/nq" > /dev/null
mkdir -p "${HOME}/.local/bin"
for bin in nq nqtail nqterm; do
    cp "${SCRIPT_DIR}/nq/${bin}" "${HOME}/.local/bin/${bin}"
    chmod +x "${HOME}/.local/bin/${bin}"
    ok "installed ${HOME}/.local/bin/${bin}"
done

# ── post-install setup ─────────────────────────────────────────────────────────
info "Creating default job directory: ${NQ_DIR}"
mkdir -p "${NQ_DIR}"
ok "${NQ_DIR} ready"

# ── PATH check ─────────────────────────────────────────────────────────────────
# pip --user usually installs to ~/.local/bin
INSTALL_DIR="${HOME}/.local/bin"
if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
    warn() { printf '\033[1;33mwarn\033[0m %s\n' "$*" >&2; }
    warn "${INSTALL_DIR} is not in your PATH."
    echo
    echo "  Add this to your shell config (~/.bashrc, ~/.zshrc, etc.):"
    echo "    export PATH=\"\${HOME}/.local/bin:\${PATH}\""
fi

echo
echo "  Run:  nqx         – open the TUI"
echo "        nq <cmd>    – enqueue a job"
