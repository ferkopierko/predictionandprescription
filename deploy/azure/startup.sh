#!/bin/sh
set -eu
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
exec python -m uvicorn hrontech.server:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips '*'
