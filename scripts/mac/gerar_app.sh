#!/bin/bash
# Gera o aplicativo de Mac: dist/Anonimizador DPU.app
#
# Equivale a scripts\gerar_executavel.bat (Windows). Etapas:
#   1. confere o ambiente virtual (.venv) e o Tesseract embutido (compila se faltar);
#   2. roda a suíte de testes (pule com --sem-testes);
#   3. gera o ícone e o aplicativo com o PyInstaller;
#   4. confere a assinatura local e roda a autoverificação do aplicativo pronto.
#
# Uso, a partir de qualquer pasta:
#     scripts/mac/gerar_app.sh [--sem-testes]

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
PY="$RAIZ/.venv/bin/python"
APP="$RAIZ/dist/Anonimizador DPU.app"

if [ ! -x "$PY" ]; then
    echo "Ambiente virtual ausente. Prepare-o antes com: scripts/mac/instalar.sh" >&2
    exit 1
fi

if [ ! -x "$RAIZ/tesseract/tesseract" ]; then
    echo "=== Tesseract embutido ausente: compilando ==="
    "$RAIZ/scripts/mac/construir_tesseract.sh"
fi

if [ "${1:-}" != "--sem-testes" ]; then
    echo "=== Testes ==="
    # Janela fora da tela: os testes de interface não piscam na área de trabalho.
    QT_QPA_PLATFORM=offscreen "$PY" -m pytest -q -p no:cacheprovider
fi

echo "=== Ícone ==="
"$PY" "$RAIZ/scripts/mac/gerar_icone.py" "$RAIZ/.build/icone/AnonimizadorDPU.icns"

echo "=== Aplicativo ==="
"$PY" -m PyInstaller "$RAIZ/scripts/mac/anonimizador_dpu_mac.spec" --noconfirm \
    --distpath "$RAIZ/dist" --workpath "$RAIZ/build" --log-level WARN

# A pasta intermediária do PyInstaller (dist/AnonimizadorDPU) não é o
# aplicativo; fica só o .app, para não haver dúvida sobre o que distribuir.
rm -rf "$RAIZ/dist/AnonimizadorDPU"

echo "=== Conferência ==="
codesign --verify --deep --strict "$APP"
echo "assinatura local: íntegra"
du -sh "$APP"
"$APP/Contents/MacOS/AnonimizadorDPU" --verificar
echo
echo "Aplicativo gerado em: $APP"
