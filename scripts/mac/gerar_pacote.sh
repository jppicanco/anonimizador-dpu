#!/bin/bash
# Gera o aplicativo E monta o pacote de distribuição (equivale a scripts\gerar_pacote.bat).
#
#   scripts/mac/gerar_pacote.sh
#
# Resultado: dist/AnonimizadorDPU-mac.dmg (principal) e dist/AnonimizadorDPU-mac.zip
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
"$DIR/gerar_app.sh" "$@"
echo
echo "=== Montando o pacote ==="
"$DIR/montar_pacote_mac.sh"
