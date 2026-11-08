#!/bin/bash
# Prepara o ambiente de desenvolvimento no Mac (equivale a scripts\instalar.bat).
#
# Usa um Python 3.13 portátil (python-build-standalone), e não o do Homebrew:
# o PyInstaller copia a biblioteca do Python para dentro do aplicativo, e a do
# Homebrew é compilada para o macOS da própria máquina (hoje, 26 ou mais
# novo) - o aplicativo deixaria de abrir em Macs com sistema anterior. O
# portátil aceita macOS 11 em diante.
#
# Uso: scripts/mac/instalar.sh

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"

PBS_DATA="20261026"
PY_VERSAO="3.13.18"
ARQUIVO="cpython-${PY_VERSAO}+${PBS_DATA}-aarch64-apple-darwin-install_only.tar.gz"
SHA="e5af2fde6a937a0e0c795a0c595c4efb70578d57463a2657c819992b9b9acbac"
URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_DATA}/${ARQUIVO//+/%2B}"

if [ "$(uname -m)" != "arm64" ]; then
    echo "Este roteiro prepara a versão para Mac com chip Apple (arm64)." >&2
    exit 1
fi

mkdir -p .build/downloads
DESTINO=".build/downloads/$ARQUIVO"
if [ ! -f "$DESTINO" ]; then
    echo "baixando Python $PY_VERSAO portátil…"
    curl -fsSL --retry 3 -o "$DESTINO.parcial" "$URL"
    mv "$DESTINO.parcial" "$DESTINO"
fi
if [ "$(shasum -a 256 "$DESTINO" | awk '{print $1}')" != "$SHA" ]; then
    echo "SHA-256 divergente para $ARQUIVO" >&2
    exit 1
fi
if [ ! -x .build/python/bin/python3.13 ]; then
    tar -xzf "$DESTINO" -C .build
fi

if [ ! -x .venv/bin/python ]; then
    echo "criando ambiente virtual .venv…"
    .build/python/bin/python3.13 -m venv .venv
fi
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r scripts/mac/requirements-mac.txt

echo
echo "Ambiente pronto. Próximos passos:"
echo "  scripts/mac/construir_tesseract.sh   compila o OCR embutido (uma vez)"
echo "  scripts/mac/executar.sh              abre o aplicativo a partir do código"
echo "  scripts/mac/testar.sh                roda a suíte de testes"
echo "  scripts/mac/gerar_pacote.sh          gera o .app e o DMG de distribuição"
