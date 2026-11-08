#!/bin/bash
# Executa a suíte automatizada de testes (equivale a scripts\testar.bat).
# As janelas dos testes de interface são desenhadas fora da tela.
set -euo pipefail
cd "$(dirname "$0")/../.."
QT_QPA_PLATFORM=offscreen exec .venv/bin/python -m pytest -rs -p no:cacheprovider "$@"
