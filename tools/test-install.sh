#!/usr/bin/env bash
# test-install.sh – Smoke-test the nqy installation pipeline inside Docker.
#
# Usage:
#   ./tools/test-install.sh              # run both tests (default)
#   ./tools/test-install.sh installer    # test the install.sh one-liner only
#   ./tools/test-install.sh pip          # test pip install . only
#
# Requirements: Docker must be installed and the daemon must be running.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DOCKERFILE="${SCRIPT_DIR}/Dockerfile.test"

info()  { printf '\n\033[1;34m══ %s\033[0m\n' "$*"; }
ok()    { printf '\033[1;32m✔  %s\033[0m\n' "$*"; }
fail()  { printf '\033[1;31m✖  %s\033[0m\n' "$*" >&2; exit 1; }

require_docker() {
    command -v docker >/dev/null 2>&1 || fail "Docker is not installed."
    docker info >/dev/null 2>&1      || fail "Docker daemon is not running."
}

run_stage() {
    local target="$1"
    local tag="nqy-test-${target}"

    info "Testing stage: ${target}"
    docker build \
        --target "${target}" \
        --tag    "${tag}" \
        --file   "${DOCKERFILE}" \
        "${REPO_ROOT}"

    # Run the image to re-execute the RUN steps; since all verification is in
    # RUN instructions, a successful build already means the tests passed.
    # We also do a quick container-run check for belt-and-suspenders.
    docker run --rm "${tag}" python3 -c "
from nqy.logic import get_nq_executable
nq = get_nq_executable()
assert nq != 'nq' or __import__('shutil').which('nq'), 'nq not found'
print('container self-check passed, nq =', nq)
"
    ok "Stage '${target}' passed"
}

require_docker

MODE="${1:-both}"

case "${MODE}" in
    installer) run_stage "test-installer" ;;
    pip)       run_stage "test-pip" ;;
    both)
        run_stage "test-installer"
        run_stage "test-pip"
        ;;
    *)
        echo "Usage: $0 [installer|pip|both]"
        exit 1
        ;;
esac

info "All requested tests passed"
