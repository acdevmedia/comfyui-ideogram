#!/usr/bin/env bash
# Runs during the image build: boot the installed copyparty and prove the login guards the outputs.
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/copyparty.sh"
fixture=$(mktemp -d)
export COPYPARTY_PORT=13923 COPYPARTY_STATE="$fixture/state" COPYPARTY_LOG="$fixture/copyparty.log" COPYPARTY_CONFIG="$fixture/copyparty.conf"
url="http://127.0.0.1:$COPYPARTY_PORT"
COPYPARTY_PID=
trap 'status=$?; [[ -z "$COPYPARTY_PID" ]] || kill "$COPYPARTY_PID" 2>/dev/null || true; ((status == 0)) || tail -n 40 "$COPYPARTY_LOG" 2>/dev/null || true; rm -rf "$fixture"' EXIT
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 30 "$@" || true; }
fail() { echo "FAIL: $1" >&2; exit 1; }
refused() { [[ "$1" =~ ^4 ]]; }

mkdir -p "$fixture/output"
python3 -c 'import sys;from PIL import Image;Image.new("RGB",(64,96),(200,40,40)).save(sys.argv[1])' "$fixture/output/portrait.png"
printf 'keep' > "$fixture/output/keep.txt"

# Missing, unresolved and unstorable logins must never leave a server running.
refuse() (
  export COPYPARTY_USERNAME="$1" COPYPARTY_PASSWORD="$2"
  start_copyparty "$fixture/output" test | grep -q 'Not started'
  [[ -z "$COPYPARTY_PID" && ! -e "$COPYPARTY_CONFIG" ]]
)
refuse '' secret || fail 'empty username'
refuse alex '' || fail 'empty password'
refuse alex '{{ RUNPOD_SECRET_COPYPARTY_SECRET }}' || fail 'unresolved password'
refuse '{{ RUNPOD_SECRET_COPYPARTY_USERNAME }}' secret || fail 'unresolved username'
refuse 'al:ex' secret || fail 'colon in username'
refuse alex ' padded' || fail 'leading space'
refuse alex 'cut  # short' || fail 'comment sequence'

password='c0rrect h#rse:b@ttery$HOME"'\''\'
export COPYPARTY_USERNAME=alex COPYPARTY_PASSWORD="$password"
start_copyparty "$fixture/output" 'Test outputs'
[[ -n "$COPYPARTY_PID" ]] || fail 'did not start with a valid login'
[[ -z "${COPYPARTY_PASSWORD:-}${COPYPARTY_USERNAME:-}" ]] || fail 'secrets left in the environment'
[[ "$(stat -c %a "$COPYPARTY_CONFIG")" == 600 ]] || fail 'config is readable by others'
if tr '\0' ' ' < "/proc/$COPYPARTY_PID/cmdline" | grep -qF 'b@ttery'; then fail 'password on the command line'; fi
for _ in $(seq 1 120); do
  [[ "$(code "$url/")" == 000 ]] || break
  python3 -c 'import time;time.sleep(0.5)'
done

login=(-u "alex:$password")
refused "$(code "$url/portrait.png")" || fail 'anonymous download allowed'
refused "$(code "$url/portrait.png" -u 'alex:wrong-password')" || fail 'wrong password allowed'
refused "$(code "$url/portrait.png" -u "someone:$password")" || fail 'wrong username allowed'
[[ "$(code "$url/portrait.png" "${login[@]}")" == 200 ]] || fail 'correct login refused'
curl -sf --max-time 30 "${login[@]}" "$url/?ls" | grep -q portrait.png || fail 'listing is missing the file'
curl -sf --max-time 30 "${login[@]}" "$url/?zip" -o "$fixture/all.zip" || fail 'zip download failed'
unzip -l "$fixture/all.zip" | grep -q portrait.png || fail 'zip is missing the file'
[[ "$(code "$url/portrait.png?th=j" "${login[@]}")" == 200 ]] || fail 'thumbnail failed'

# Read-only: nothing can be added, replaced or removed, even with the login.
refused "$(code -X PUT --data-binary new "$url/new.txt" "${login[@]}")" || fail 'upload allowed'
refused "$(code -X POST "$url/keep.txt?delete" "${login[@]}")" || fail 'delete allowed'
[[ -e "$fixture/output/keep.txt" && ! -e "$fixture/output/new.txt" ]] || fail 'files changed'
[[ ! -e "$fixture/output/.hist" ]] || fail 'thumbnails landed in the output folder'
command -v zip >/dev/null && command -v aws >/dev/null || fail 'zip or aws is missing'
echo 'PASS: copyparty needs both username and password and serves read-only galleries and ZIPs; zip, unzip and aws are installed.'
