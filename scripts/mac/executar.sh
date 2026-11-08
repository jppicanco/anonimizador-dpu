#!/bin/bash
# Abre o Anonimizador DPU a partir do código-fonte (equivale a scripts\executar.bat).
set -euo pipefail
cd "$(dirname "$0")/../.."
exec .venv/bin/python -m anonimizador_dpu.app.main "$@"
