#!/usr/bin/env sh
set -eu

if [ "$#" -ne 3 ]; then
  echo "usage: $0 MACHINE_METADATA RUNTIME_ROOT CONFIRM (empty RUNTIME_ROOT uses PIPELINE_RUNTIME_DIR)" >&2
  exit 2
fi
if [ "$3" != "RUN-DESIGNATED-MACHINE-EXPERIMENTS" ]; then
  echo "explicit execution confirmation is required" >&2
  exit 2
fi

repository="$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd -P)"
case "$1" in
  /*) machine_metadata="$1" ;;
  *) machine_metadata="$(pwd)/$1" ;;
esac
runtime_root="${2:-${PIPELINE_RUNTIME_DIR:-}}"
if [ -z "$runtime_root" ]; then
  echo "provide RUNTIME_ROOT or PIPELINE_RUNTIME_DIR" >&2
  exit 2
fi
pipeline_python="${PIPELINE_PYTHON:-$repository/.venv/bin/python}"
cd -- "$repository"
exec "$pipeline_python" -m iot_energy_pipeline.fixture_acceptance \
  --machine-metadata "$machine_metadata" \
  --runtime-root "$runtime_root" \
  --repository "$repository" \
  --python "$pipeline_python" \
  --confirm "$3"
