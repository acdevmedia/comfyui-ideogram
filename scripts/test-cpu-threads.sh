#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/cpu-threads.sh"
fixture=$(mktemp -d)
trap 'rm -rf "$fixture"' EXIT
nproc() { echo 192; }
check() (
  unset OMP_NUM_THREADS MKL_NUM_THREADS
  configure_cpu_threads "$fixture"
  [[ "$OMP_NUM_THREADS" == "$1" && "$MKL_NUM_THREADS" == "$1" ]]
)
# A 192-core host with a 20-CPU Pod must not spawn 192 worker threads.
printf '2000000 100000\n' > "$fixture/cpu.max"
check 20
printf '50000 100000\n' > "$fixture/cpu.max"
check 1
printf 'max 100000\n' > "$fixture/cpu.max"
check 192
printf '2000000 0\n' > "$fixture/cpu.max"
check 192
printf '2000000 100000\n' > "$fixture/cpu.max"
( nproc() { echo 8; }; check 8 )
rm "$fixture/cpu.max"
mkdir "$fixture/cpu"
printf '2000000\n' > "$fixture/cpu/cpu.cfs_quota_us"
printf '100000\n' > "$fixture/cpu/cpu.cfs_period_us"
check 20
printf '%s\n' -1 > "$fixture/cpu/cpu.cfs_quota_us"
check 192
rm -r "$fixture/cpu"
check 192
(
  export OMP_NUM_THREADS=4 MKL_NUM_THREADS=2
  configure_cpu_threads "$fixture"
  [[ "$OMP_NUM_THREADS" == 4 && "$MKL_NUM_THREADS" == 2 ]]
)
(
  export OMP_NUM_THREADS=4
  unset MKL_NUM_THREADS
  configure_cpu_threads "$fixture"
  [[ "$MKL_NUM_THREADS" == 4 ]]
)
echo 'PASS: CPU quota sizing, affinity, fallback and explicit thread overrides.'
