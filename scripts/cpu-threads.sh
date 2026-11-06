#!/usr/bin/env bash
# Source before starting Python so PyTorch/OpenMP sees the container CPU budget.
configure_cpu_threads() {
  local cgroup_root="${1:-/sys/fs/cgroup}" quota period threads available
  if [[ -z "${OMP_NUM_THREADS:-}" ]]; then
    available=$(nproc)
    threads=$available
    if { read -r quota period < "$cgroup_root/cpu.max"; } 2>/dev/null; then :; else
      quota=$(cat "$cgroup_root/cpu/cpu.cfs_quota_us" 2>/dev/null || echo max)
      period=$(cat "$cgroup_root/cpu/cpu.cfs_period_us" 2>/dev/null || echo 100000)
    fi
    if [[ "$quota" =~ ^[0-9]+$ && "$period" =~ ^[0-9]+$ ]] && (( period > 0 )); then
      threads=$(( quota / period ))
      # Fractional CPU quotas still need one thread; respect affinity as well.
      (( threads >= 1 )) || threads=1
      (( threads <= available )) || threads=$available
    fi
    export OMP_NUM_THREADS=$threads
  fi
  export MKL_NUM_THREADS=${MKL_NUM_THREADS:-$OMP_NUM_THREADS}
  echo "[cpu] OMP_NUM_THREADS=$OMP_NUM_THREADS MKL_NUM_THREADS=$MKL_NUM_THREADS (automatic container CPU budget unless overridden)."
}
