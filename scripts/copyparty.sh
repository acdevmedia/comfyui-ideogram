#!/usr/bin/env bash
# Source at startup, after the models are ready. Serves ComfyUI's output folder read-only on port 3923:
# browse it as a gallery and download single files or ZIPs through the Runpod proxy. The login comes from
# the COPYPARTY_USERNAME and COPYPARTY_PASSWORD secrets; without both, nothing is served at all.
start_copyparty() {
  local output="$1" title="$2" user="${COPYPARTY_USERNAME:-}" password="${COPYPARTY_PASSWORD:-}"
  local port="${COPYPARTY_PORT:-3923}" state="${COPYPARTY_STATE:-/workspace/.copyparty}" log="${COPYPARTY_LOG:-/workspace/logs/copyparty.log}"
  local config="${COPYPARTY_CONFIG:-/run/copyparty.conf}"
  # ComfyUI and everything after it have no use for these.
  unset COPYPARTY_USERNAME COPYPARTY_PASSWORD
  if [[ -z "$user" || -z "$password" || "$user" == *"{{"* || "$password" == *"{{"* ]]; then
    echo '[copyparty] Not started: COPYPARTY_USERNAME or COPYPARTY_PASSWORD is empty or unresolved. Create those Runpod Secrets to use the file browser on port 3923. ComfyUI is unaffected.'
    return 0
  fi
  # The config format strips outer spaces, ends a value at two spaces and a hash, and splits accounts on the
  # first colon. Refuse a login it cannot hold rather than serve one that differs from the secret.
  if [[ "$user" =~ [[:space:]:] || "$password" != "${password#[[:space:]]}" || "$password" != "${password%[[:space:]]}" \
        || "$password" == *"  #"* || "$password" == *$'\n'* ]]; then
    echo '[copyparty] Not started: the username may not contain spaces or colons, and the password may not start or end with a space or contain a newline or two spaces before a #. ComfyUI is unaffected.'
    return 0
  fi
  if ! mkdir -p "$output" "$state" "$(dirname "$log")" || ! ( umask 077; cat > "$config" <<CONF
[global]
  i: 0.0.0.0
  p: $port
  usernames
  hist: $state
  name: $title
  theme: 2
  grid
  sort: -ts
  gsel
  no-robots
  th-mt: 2
  mtag-mt: 1
  xff-src: any
  rproxy: -1

[accounts]
  $user: $password

[/]
  $output
  accs:
    r: $user
CONF
  ); then
    echo '[copyparty] Not started: could not prepare its folders or configuration. ComfyUI is unaffected.'
    return 0
  fi
  python3 -m copyparty -c "$config" </dev/null >>"$log" 2>&1 &
  COPYPARTY_PID=$!
  echo "[copyparty] Serving $output read-only on port $port${RUNPOD_POD_ID:+: https://$RUNPOD_POD_ID-$port.proxy.runpod.net}. Sign in with your Runpod secrets. Log: $log"
}
