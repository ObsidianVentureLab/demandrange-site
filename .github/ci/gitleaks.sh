#!/usr/bin/env bash
# Secret scan with a pinned, checksum-verified gitleaks CLI (no GitHub App, no licence key).
#   .github/ci/gitleaks.sh <repo-dir> [extra `gitleaks detect` args, e.g. --log-opts=BASE..HEAD]
# Exit 1 when a leak is found or the download does not match the pinned checksum.
set -euo pipefail
GITLEAKS_VERSION="8.21.2"
GITLEAKS_SHA256="5bc41815076e6ed6ef8fbecc9d9b75bcae31f39029ceb55da08086315316e3ba"  # gitleaks_8.21.2_linux_x64.tar.gz
REPO_DIR="${1:?usage: gitleaks.sh <repo-dir> [detect args]}"
shift || true
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) ;;
  *) echo "gitleaks.sh: pinned checksum is for linux_x64 only" >&2; exit 2 ;;
esac
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
url="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz"
curl -sSfL --retry 4 --retry-delay 3 --retry-all-errors -o "$tmp/gitleaks.tar.gz" "$url"   # --retry-all-errors: plain --retry skips connection resets (curl exit 56)
echo "${GITLEAKS_SHA256}  $tmp/gitleaks.tar.gz" | sha256sum -c - >/dev/null
tar -xzf "$tmp/gitleaks.tar.gz" -C "$tmp" gitleaks
echo "gitleaks $("$tmp/gitleaks" version) (pinned, checksum verified)"
"$tmp/gitleaks" detect --source "$REPO_DIR" --redact --no-banner --exit-code 1 "$@"
