#!/bin/bash
# Monta o pacote de distribuição para Mac: dist/AnonimizadorDPU-mac.dmg e .zip
#
# Equivale a scripts/montar_pacote.py (Windows). O conteúdo é o mesmo do ZIP
# Windows - aplicativo, documentação, código-fonte (AGPL), INSTALAR.txt e
# LICENCAS.txt -, no formato que o Mac espera: uma imagem de disco (.dmg) com
# o atalho "Aplicativos" para arrastar o programa. O ZIP sai como alternativa.
#
# Pré-requisito: dist/Anonimizador DPU.app (scripts/mac/gerar_app.sh).
#
# Observação: o ZIP é feito com `ditto`, e não com o zipfile do Python como no
# Windows, porque o .app contém links simbólicos e assinatura de código que um
# ZIP comum não preserva - o aplicativo chegaria "danificado".

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$RAIZ"
APP="$RAIZ/dist/Anonimizador DPU.app"
MONTAGEM="$RAIZ/dist/pacote-mac"
PACOTE="$MONTAGEM/AnonimizadorDPU"   # nome da pasta que o colega vê no ZIP
DMG="$RAIZ/dist/AnonimizadorDPU-mac.dmg"
ZIP="$RAIZ/dist/AnonimizadorDPU-mac.zip"

if [ ! -d "$APP" ]; then
    echo "Aplicativo não encontrado. Gere-o antes: scripts/mac/gerar_app.sh" >&2
    exit 1
fi
codesign --verify --deep --strict "$APP"

rm -rf "$MONTAGEM" "$DMG" "$ZIP"
mkdir -p "$PACOTE/documentacao" "$PACOTE/codigo-fonte"

echo "copiando aplicativo…"
ditto "$APP" "$PACOTE/Anonimizador DPU.app"

echo "copiando instruções, licenças e documentação…"
cp scripts/mac/pacote/INSTALAR-mac.txt "$PACOTE/INSTALAR.txt"
cp scripts/mac/pacote/LICENCAS-mac.txt "$PACOTE/LICENCAS.txt"
for doc in README.md docs/MAC.md docs/MANUAL_USUARIO.md docs/LIMITACOES.md \
           docs/SEGURANCA.md docs/ARQUITETURA.md docs/TESTES.md; do
    cp "$doc" "$PACOTE/documentacao/"
done

echo "copiando código-fonte…"
rsync -a --exclude "__pycache__" --exclude "*.pyc" --exclude ".pytest_cache" \
    anonimizador_dpu tests scripts docs "$PACOTE/codigo-fonte/"
cp README.md LICENSE requirements.txt requirements-dev.txt pyproject.toml \
    "$PACOTE/codigo-fonte/"

echo "compactando ZIP…"
ditto -c -k --sequesterRsrc --keepParent "$PACOTE" "$ZIP"

echo "gerando DMG…"
ln -s /Applications "$PACOTE/Aplicativos"
hdiutil create -quiet -volname "Anonimizador DPU" -srcfolder "$PACOTE" \
    -fs HFS+ -format UDZO -ov "$DMG"

# ---------------------------------------------------------------- conferência
# Monta a imagem recém-criada e confere o aplicativo de dentro dela.
echo "conferindo o DMG…"
PONTO="$(mktemp -d)"
hdiutil attach -quiet -nobrowse -readonly -mountpoint "$PONTO" "$DMG"
trap 'hdiutil detach -quiet "$PONTO" >/dev/null 2>&1 || true; rmdir "$PONTO" 2>/dev/null || true' EXIT
codesign --verify --deep --strict "$PONTO/Anonimizador DPU.app"
"$PONTO/Anonimizador DPU.app/Contents/MacOS/AnonimizadorDPU" --verificar >/dev/null
echo "aplicativo dentro do DMG: assinatura íntegra e autoverificação aprovada"

echo
du -sh "$DMG" "$ZIP"
echo "Pacote pronto. Teste em outro Mac antes de distribuir."
