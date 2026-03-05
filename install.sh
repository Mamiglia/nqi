#!/usr/bin/env bash
# install.sh – Install nqi (TUI) + nq/nqtail/nqterm (C utilities)
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

have_cmd() {
    command -v "$1" >/dev/null 2>&1
}

have_nq_suite() {
    have_cmd nq && have_cmd nqtail && have_cmd nqterm
}

run_privileged() {
    if [[ "${EUID}" -eq 0 ]]; then
        "$@"
        return $?
    fi
    if have_cmd sudo && sudo -n true >/dev/null 2>&1; then
        sudo "$@"
        return $?
    fi
    return 1
}

detect_pkg_manager() {
    if have_cmd apt-get && have_cmd apt-cache; then
        echo "apt"
    elif have_cmd dnf; then
        echo "dnf"
    elif have_cmd yum; then
        echo "yum"
    elif have_cmd pacman; then
        echo "pacman"
    elif have_cmd zypper; then
        echo "zypper"
    elif have_cmd apk; then
        echo "apk"
    else
        echo "none"
    fi
}

pkg_has_nq() {
    local pm="$1"
    case "$pm" in
        apt) apt-cache show nq >/dev/null 2>&1 ;;
        dnf) dnf -q info nq >/dev/null 2>&1 ;;
        yum) yum -q info nq >/dev/null 2>&1 ;;
        pacman) pacman -Si nq >/dev/null 2>&1 ;;
        zypper) zypper -n info nq >/dev/null 2>&1 ;;
        apk) apk search -x nq >/dev/null 2>&1 ;;
        *) return 1 ;;
    esac
}

pkg_install_nq() {
    local pm="$1"
    case "$pm" in
        apt)
            run_privileged apt-get update >/dev/null && run_privileged apt-get install -y nq
            ;;
        dnf)
            run_privileged dnf install -y nq
            ;;
        yum)
            run_privileged yum install -y nq
            ;;
        pacman)
            run_privileged pacman -Sy --noconfirm nq
            ;;
        zypper)
            run_privileged zypper -n install nq
            ;;
        apk)
            run_privileged apk add nq
            ;;
        *)
            return 1
            ;;
    esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# ── pre-flight checks ────────────────────────────────────────────────────────
require python3

python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" \
    || die "Python 3.8 or newer is required."

# ── install nqi (setup.py compiles and bundles nq into the wheel) ─────────────
info "Installing nqi..."

if command -v pipx >/dev/null 2>&1; then
    pipx install --force "${SCRIPT_DIR}"
    ok "nqi installed via pipx"
else
    python3 -m pip install --user "${SCRIPT_DIR}"
    ok "nqi installed via pip --user"
fi

# ── install nq utilities: system package first, local build last ─────────────
info "Ensuring nq utilities are available..."

if have_nq_suite; then
    ok "using existing system nq/nqtail/nqterm from PATH"
else
    PM="$(detect_pkg_manager)"
    if [[ "${PM}" != "none" ]] && pkg_has_nq "${PM}"; then
        info "Found 'nq' in ${PM}; attempting package install"
        if pkg_install_nq "${PM}"; then
            ok "installed nq via ${PM}"
        else
            warn "Could not install nq via ${PM} (missing privileges or install failed)."
        fi
    else
        warn "No supported package manager entry for 'nq' was found."
    fi

    if ! have_nq_suite; then
        info "Falling back to local build of nq utilities"
        require make
        if ! have_cmd gcc && ! have_cmd clang; then
            die "No C compiler found (gcc or clang required for local nq build)."
        fi

        BIN_DIR="${HOME}/.local/bin"
        LIBEXEC_DIR="${HOME}/.local/lib/nqi/bin"
        mkdir -p "${BIN_DIR}" "${LIBEXEC_DIR}"

        make -C "${SCRIPT_DIR}/nq" > /dev/null
        for bin in nq nqtail nqterm; do
            cp "${SCRIPT_DIR}/nq/${bin}" "${LIBEXEC_DIR}/${bin}"
            chmod +x "${LIBEXEC_DIR}/${bin}"

            cat > "${BIN_DIR}/${bin}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

: "${NQDIR:=${HOME}/.local/share/nq}"
export NQDIR

exec "${HOME}/.local/lib/nqi/bin/__BIN__" "$@"
EOF
            sed -i "s/__BIN__/${bin}/g" "${BIN_DIR}/${bin}"
            chmod +x "${BIN_DIR}/${bin}"
            ok "installed ${BIN_DIR}/${bin} (wrapper)"
        done
    fi
fi

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
echo "  Run:  nqi         – open the TUI"
echo "        nq <cmd>    – enqueue a job"
