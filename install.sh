#!/usr/bin/env bash
# install.sh – Install nqy (TUI) + nq/nqtail/nqterm (C utilities)
#
# Usage:
#   ./install.sh

set -euo pipefail

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==> \033[0m%s\n' "$*"; }
ok()    { printf '\033[1;32m ok \033[0m%s\n' "$*"; }
warn()  { printf '\033[1;33mwarn\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31merr \033[0m%s\n' "$*" >&2; exit 1; }

require() {
    command -v "$1" >/dev/null 2>&1 || die "Required tool not found: $1"
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ── pre-flight checks ────────────────────────────────────────────────────────
require make
require python3
if ! command -v gcc >/dev/null 2>&1 && ! command -v clang >/dev/null 2>&1; then
    die "No C compiler found (gcc or clang is required to build nq)."
fi

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" \
    || die "Python 3.8 or newer is required."

# ── install nqy (setup.py compiles and bundles nq into the wheel) ─────────────
info "Installing nqy..."

if command -v pipx >/dev/null 2>&1; then
    pipx install --force "${SCRIPT_DIR}"
    ok "nqy installed via pipx"
else
    python3 -m pip install --user "${SCRIPT_DIR}"
    ok "nqy installed via pip --user"
fi

# ── install nq C utilities + wrappers ─────────────────────────────────────────
# Keep upstream binaries unmodified under ~/.local/lib/nqy/bin, and expose
# lightweight wrappers in ~/.local/bin that set a shared default NQDIR.
info "Installing nq C utilities and wrappers..."
make -C "${SCRIPT_DIR}/nq" > /dev/null

BIN_DIR="${HOME}/.local/bin"
LIBEXEC_DIR="${HOME}/.local/lib/nqy/bin"
mkdir -p "${BIN_DIR}" "${LIBEXEC_DIR}"

for bin in nq nqtail nqterm; do
    cp "${SCRIPT_DIR}/nq/${bin}" "${LIBEXEC_DIR}/${bin}"
    chmod +x "${LIBEXEC_DIR}/${bin}"

    cat > "${BIN_DIR}/${bin}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

: "${NQDIR:=${HOME}/.local/share/nq}"
export NQDIR

exec "${HOME}/.local/lib/nqy/bin/__BIN__" "$@"
EOF
    sed -i "s/__BIN__/${bin}/g" "${BIN_DIR}/${bin}"
    chmod +x "${BIN_DIR}/${bin}"
    ok "installed ${BIN_DIR}/${bin} (wrapper)"
done

# ── post-install setup ────────────────────────────────────────────────────────
NQ_DIR="${HOME}/.local/share/nq"
info "Creating default job directory: ${NQ_DIR}"
mkdir -p "${NQ_DIR}"
ok "${NQ_DIR} ready"

# ── PATH check ────────────────────────────────────────────────────────────────
INSTALL_DIR="${HOME}/.local/bin"
if [[ ":${PATH}:" != *":${INSTALL_DIR}:"* ]]; then
    warn "${INSTALL_DIR} is not in your PATH."
    echo
    echo "  Add this to your shell config (~/.bashrc, ~/.zshrc, etc.):"
    echo "    export PATH=\"\${HOME}/.local/bin:\${PATH}\""
fi

echo
echo "  Run:  nqy         – open the TUI"
echo "        nq <cmd>    – enqueue a job"
