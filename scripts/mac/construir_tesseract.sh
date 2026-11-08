#!/bin/bash
# Compila o Tesseract OCR para ser embutido no aplicativo do Mac.
#
# Por que compilar em vez de copiar o Tesseract do Homebrew: os pacotes do
# Homebrew são gerados para a versão do macOS da máquina que os instalou (hoje,
# macOS 26 ou mais novo) e dependem de uma dúzia de bibliotecas em
# /opt/homebrew. Copiados para dentro do aplicativo, deixariam de abrir nos
# Macs dos colegas com macOS mais antigo ou sem Homebrew.
#
# O resultado é UM executável autocontido (libpng, Leptonica e Tesseract
# ligados estaticamente), que depende apenas de bibliotecas do próprio macOS,
# mais os dados de idioma por, eng e osd — os mesmos três do pacote Windows.
#
# Nada aqui roda durante o uso do aplicativo: é etapa de construção, feita uma
# vez, em máquina com internet. Todos os downloads são conferidos por SHA-256.
#
# Uso, a partir da raiz do projeto:
#     scripts/mac/construir_tesseract.sh
# Resultado em tesseract/ na raiz do projeto (tesseract, tessdata/, licencas/),
# o mesmo lugar e o mesmo formato que o aplicativo procura no Windows: ao lado
# do programa. A pasta não é versionada (.gitignore).

set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD="$RAIZ/.build"
DOWNLOADS="$BUILD/downloads"
FONTES="$BUILD/fontes"
PREFIXO="$BUILD/tesseract-prefixo"
DIST="$RAIZ/tesseract"

# Versão mínima de macOS do executável gerado. Fica abaixo da exigida pelo
# Qt/PySide6, de modo que o Tesseract nunca seja o fator limitante.
export MACOSX_DEPLOYMENT_TARGET="12.0"
ARQUITETURA="arm64"

# CMake e Ninja vêm do ambiente virtual do projeto (pip install cmake ninja),
# para não exigir Homebrew nem instalar nada no sistema.
VENV_BIN="$RAIZ/.venv/bin"
CMAKE="$VENV_BIN/cmake"
NINJA="$VENV_BIN/ninja"
for ferramenta in "$CMAKE" "$NINJA"; do
    if [ ! -x "$ferramenta" ]; then
        echo "Ferramenta ausente: $ferramenta" >&2
        echo "Rode antes: .venv/bin/python -m pip install -r scripts/mac/requirements-mac.txt" >&2
        exit 1
    fi
done

LIBPNG_VERSAO="1.6.59"
LIBPNG_URL="https://github.com/pnggroup/libpng/archive/refs/tags/v${LIBPNG_VERSAO}.tar.gz"
LIBPNG_SHA="2540302a1844ad2b2b501977abecfa850f265f97b78f065a712ab4074a89f5b5"

# A Leptonica guarda sua fonte de bitmap interna em formato TIFF. Sem libtiff,
# o Tesseract imprime "Error in bmfCreate: font pixa not made" a cada execução
# — e o pytesseract, que junta stdout e stderr, passa a listar essas linhas
# como se fossem idiomas instalados.
# E a Leptonica só habilita a leitura de TIFF se houver também libjpeg.
LIBJPEG_VERSAO="3.2.1"
LIBJPEG_URL="https://github.com/libjpeg-turbo/libjpeg-turbo/releases/download/${LIBJPEG_VERSAO}/libjpeg-turbo-${LIBJPEG_VERSAO}.tar.gz"
LIBJPEG_SHA="c27ad72a68da151177929aa969ae773a2da5ac2af9ce946079314fdac8cece7f"

LIBTIFF_VERSAO="4.7.2"
LIBTIFF_URL="https://download.osgeo.org/libtiff/tiff-${LIBTIFF_VERSAO}.tar.gz"
LIBTIFF_SHA="672bd7d10aee4606171afb864f3570b83340f6a33e2c186dc0512f7145ffdf6a"

LEPTONICA_VERSAO="1.87.0"
LEPTONICA_URL="https://github.com/DanBloomberg/leptonica/releases/download/${LEPTONICA_VERSAO}/leptonica-${LEPTONICA_VERSAO}.tar.gz"
LEPTONICA_SHA="c73363397f96eb1295602bf44d708a994ad42046c791bf03ea0505d829bdb6a7"

TESSERACT_VERSAO="5.5.4"
TESSERACT_URL="https://github.com/tesseract-ocr/tesseract/archive/refs/tags/${TESSERACT_VERSAO}.tar.gz"
TESSERACT_SHA="a8dbf8b8c8ee427ff6ad1d99116502feaf59440af1adb893caf60a6576826cf4"

# Dados de idioma "padrão" (tessdata 4.1.0: modelo LSTM + legado).
TESSDATA_URL="https://github.com/tesseract-ocr/tessdata/raw/4.1.0"
IDIOMAS=(
    "por 016c6a371bb1e4c48fe521908cf3ba3d751fade0ab846ad5d4086b563f5c528c"
    "eng daa0c97d651c19fba3b25e81317cd697e9908c8208090c94c3905381c23fc047"
    "osd e19f2ae860792fdf372cf48d8ce70ae5da3c4052962fe22e9de1f680c374bb0e"
)

baixar() {  # baixar URL DESTINO SHA256
    local url="$1" destino="$2" esperado="$3"
    if [ ! -f "$destino" ]; then
        echo "baixando $(basename "$destino")…"
        curl -fsSL --retry 3 -o "$destino.parcial" "$url"
        mv "$destino.parcial" "$destino"
    fi
    local obtido
    obtido="$(shasum -a 256 "$destino" | awk '{print $1}')"
    if [ "$obtido" != "$esperado" ]; then
        echo "SHA-256 divergente para $(basename "$destino")" >&2
        echo "  esperado: $esperado" >&2
        echo "  obtido:   $obtido" >&2
        exit 1
    fi
}

extrair() {  # extrair ARQUIVO PASTA_DESTINO
    rm -rf "$2"
    mkdir -p "$2"
    tar -xzf "$1" -C "$2" --strip-components=1
}

# Impede que o CMake encontre, por engano, as bibliotecas do Homebrew: elas
# exigem macOS 26 e não existem nas máquinas dos colegas.
IGNORAR="/opt/homebrew;/usr/local"
unset PKG_CONFIG_PATH
export PKG_CONFIG_LIBDIR="$PREFIXO/lib/pkgconfig"

COMUNS=(
    -G Ninja
    -DCMAKE_MAKE_PROGRAM="$NINJA"
    -DCMAKE_BUILD_TYPE=Release
    -DCMAKE_OSX_ARCHITECTURES="$ARQUITETURA"
    -DCMAKE_OSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET"
    -DCMAKE_INSTALL_PREFIX="$PREFIXO"
    -DCMAKE_PREFIX_PATH="$PREFIXO"
    -DCMAKE_IGNORE_PREFIX_PATH="$IGNORAR"
    -DCMAKE_FIND_FRAMEWORK=LAST
    -DBUILD_SHARED_LIBS=OFF
)

mkdir -p "$DOWNLOADS" "$FONTES"
rm -rf "$PREFIXO" "$DIST"

baixar "$LIBPNG_URL" "$DOWNLOADS/libpng-$LIBPNG_VERSAO.tar.gz" "$LIBPNG_SHA"
baixar "$LIBJPEG_URL" "$DOWNLOADS/libjpeg-turbo-$LIBJPEG_VERSAO.tar.gz" "$LIBJPEG_SHA"
baixar "$LIBTIFF_URL" "$DOWNLOADS/tiff-$LIBTIFF_VERSAO.tar.gz" "$LIBTIFF_SHA"
baixar "$LEPTONICA_URL" "$DOWNLOADS/leptonica-$LEPTONICA_VERSAO.tar.gz" "$LEPTONICA_SHA"
baixar "$TESSERACT_URL" "$DOWNLOADS/tesseract-$TESSERACT_VERSAO.tar.gz" "$TESSERACT_SHA"
for item in "${IDIOMAS[@]}"; do
    read -r idioma sha <<<"$item"
    baixar "$TESSDATA_URL/$idioma.traineddata" "$DOWNLOADS/$idioma.traineddata" "$sha"
done

# ------------------------------------------------------------------ libpng
echo "=== libpng $LIBPNG_VERSAO ==="
extrair "$DOWNLOADS/libpng-$LIBPNG_VERSAO.tar.gz" "$FONTES/libpng"
"$CMAKE" -S "$FONTES/libpng" -B "$FONTES/libpng/build" "${COMUNS[@]}" \
    -DPNG_SHARED=OFF -DPNG_STATIC=ON -DPNG_FRAMEWORK=OFF \
    -DPNG_TESTS=OFF -DPNG_TOOLS=OFF \
    >"$FONTES/libpng.cmake.log"
"$CMAKE" --build "$FONTES/libpng/build" --target install >"$FONTES/libpng.build.log"

# ------------------------------------------------------------ libjpeg-turbo
echo "=== libjpeg-turbo $LIBJPEG_VERSAO ==="
extrair "$DOWNLOADS/libjpeg-turbo-$LIBJPEG_VERSAO.tar.gz" "$FONTES/libjpeg"
"$CMAKE" -S "$FONTES/libjpeg" -B "$FONTES/libjpeg/build" "${COMUNS[@]}" \
    -DENABLE_SHARED=OFF -DENABLE_STATIC=ON -DWITH_TURBOJPEG=OFF \
    -DWITH_TOOLS=OFF -DWITH_TESTS=OFF -DWITH_SIMD=OFF \
    -DCMAKE_INSTALL_LIBDIR=lib \
    >"$FONTES/libjpeg.cmake.log"
"$CMAKE" --build "$FONTES/libjpeg/build" --target install >"$FONTES/libjpeg.build.log"

# ----------------------------------------------------------------- libtiff
# Só com zlib (do sistema): os demais codecs não são necessários.
echo "=== libtiff $LIBTIFF_VERSAO ==="
extrair "$DOWNLOADS/tiff-$LIBTIFF_VERSAO.tar.gz" "$FONTES/libtiff"
"$CMAKE" -S "$FONTES/libtiff" -B "$FONTES/libtiff/build" "${COMUNS[@]}" \
    -Dtiff-tools=OFF -Dtiff-tests=OFF -Dtiff-contrib=OFF -Dtiff-docs=OFF \
    -Dcxx=OFF -Dzlib=ON -Dlibdeflate=OFF -Djpeg=OFF -Dold-jpeg=OFF \
    -Djpeg12=OFF -Djbig=OFF -Dlerc=OFF -Dlzma=OFF -Dzstd=OFF -Dwebp=OFF \
    >"$FONTES/libtiff.cmake.log"
"$CMAKE" --build "$FONTES/libtiff/build" --target install >"$FONTES/libtiff.build.log"
# A configuração CMake exportada pela libtiff declara a dependência como o alvo
# "ZLIB::ZLIB", que não existe nos projetos consumidores e quebra a
# configuração do Tesseract. Sem ela, a Leptonica e o Tesseract recorrem à
# busca tradicional (caminho do libtiff.a), e o zlib do sistema já entra pela
# própria Leptonica.
rm -rf "$PREFIXO/lib/cmake/tiff"

# --------------------------------------------------------------- Leptonica
echo "=== Leptonica $LEPTONICA_VERSAO ==="
extrair "$DOWNLOADS/leptonica-$LEPTONICA_VERSAO.tar.gz" "$FONTES/leptonica"
"$CMAKE" -S "$FONTES/leptonica" -B "$FONTES/leptonica/build" "${COMUNS[@]}" \
    -DSW_BUILD=OFF -DBUILD_PROG=OFF \
    -DENABLE_ZLIB=ON -DENABLE_PNG=ON -DENABLE_TIFF=ON -DENABLE_JPEG=ON \
    -DENABLE_GIF=OFF -DENABLE_WEBP=OFF -DENABLE_OPENJPEG=OFF \
    -DJPEG_LIBRARY="$PREFIXO/lib/libjpeg.a" \
    -DJPEG_INCLUDE_DIR="$PREFIXO/include" \
    -DPNG_LIBRARY="$PREFIXO/lib/libpng16.a" \
    -DPNG_PNG_INCLUDE_DIR="$PREFIXO/include" \
    -DTIFF_LIBRARY="$PREFIXO/lib/libtiff.a" \
    -DTIFF_INCLUDE_DIR="$PREFIXO/include" \
    >"$FONTES/leptonica.cmake.log"
"$CMAKE" --build "$FONTES/leptonica/build" --target install >"$FONTES/leptonica.build.log"

# --------------------------------------------------------------- Tesseract
# Sem libcurl (o Tesseract não poderá ler endereços da internet), sem
# libarchive e sem as ferramentas de treinamento.
echo "=== Tesseract $TESSERACT_VERSAO ==="
extrair "$DOWNLOADS/tesseract-$TESSERACT_VERSAO.tar.gz" "$FONTES/tesseract"
"$CMAKE" -S "$FONTES/tesseract" -B "$FONTES/tesseract/build" "${COMUNS[@]}" \
    -DLeptonica_DIR="$PREFIXO/lib/cmake/leptonica" \
    -DBUILD_TRAINING_TOOLS=OFF -DBUILD_TESTS=OFF \
    -DDISABLE_CURL=ON -DDISABLE_ARCHIVE=ON -DDISABLE_TIFF=OFF \
    -DTIFF_LIBRARY="$PREFIXO/lib/libtiff.a" \
    -DTIFF_INCLUDE_DIR="$PREFIXO/include" \
    -DGRAPHICS_DISABLED=ON -DOPENMP_BUILD=OFF \
    -DINSTALL_CONFIGS=ON \
    >"$FONTES/tesseract.cmake.log"
"$CMAKE" --build "$FONTES/tesseract/build" --target install >"$FONTES/tesseract.build.log"

# --------------------------------------------------------- distribuição
mkdir -p "$DIST/tessdata" "$DIST/licencas"
cp "$PREFIXO/bin/tesseract" "$DIST/tesseract"
strip -x "$DIST/tesseract"
# `strip` invalida a assinatura que o ligador aplica; no Apple Silicon todo
# executável precisa estar assinado, ainda que localmente.
codesign --force --sign - "$DIST/tesseract"

for item in "${IDIOMAS[@]}"; do
    read -r idioma _ <<<"$item"
    cp "$DOWNLOADS/$idioma.traineddata" "$DIST/tessdata/"
done
# O pytesseract pede a saída em TSV, o que o Tesseract resolve lendo
# tessdata/configs/tsv. Sem esta pasta, o OCR falha.
cp -R "$PREFIXO/share/tessdata/configs" "$DIST/tessdata/configs"

cp "$FONTES/tesseract/LICENSE" "$DIST/licencas/tesseract-LICENSE.txt"
cp "$FONTES/leptonica/leptonica-license.txt" "$DIST/licencas/leptonica-LICENSE.txt" 2>/dev/null \
    || cp "$FONTES/leptonica/LICENSE" "$DIST/licencas/leptonica-LICENSE.txt"
cp "$FONTES/libpng/LICENSE" "$DIST/licencas/libpng-LICENSE.txt"
cp "$FONTES/libtiff/LICENSE.md" "$DIST/licencas/libtiff-LICENSE.md"
cp "$FONTES/libjpeg/LICENSE.md" "$DIST/licencas/libjpeg-turbo-LICENSE.md"
cp "$FONTES/libjpeg/README.ijg" "$DIST/licencas/libjpeg-turbo-README.ijg"
curl -fsSL --retry 3 -o "$DIST/licencas/tessdata-LICENSE.txt" "$TESSDATA_URL/LICENSE" || true

# ------------------------------------------------------------- conferência
echo
echo "=== conferência ==="
echo "dependências do executável (devem ser só do sistema):"
otool -L "$DIST/tesseract" | tail -n +2
if otool -L "$DIST/tesseract" | tail -n +2 | grep -v -E "^\s+(/usr/lib/|/System/Library/)" | grep -q .; then
    echo "ERRO: o executável depende de biblioteca fora do sistema." >&2
    exit 1
fi
otool -l "$DIST/tesseract" | grep -A4 LC_BUILD_VERSION | grep -E "minos|sdk"
TESSDATA_PREFIX="$DIST/tessdata" "$DIST/tesseract" --version 2>&1 | head -4
# O pytesseract lê stdout e stderr juntos: qualquer linha de erro aqui
# apareceria na interface como se fosse um idioma instalado.
SAIDA_IDIOMAS="$(TESSDATA_PREFIX="$DIST/tessdata" "$DIST/tesseract" --list-langs 2>&1)"
echo "$SAIDA_IDIOMAS"
if echo "$SAIDA_IDIOMAS" | grep -q -i "error"; then
    echo "ERRO: o Tesseract emitiu mensagens de erro ao listar os idiomas." >&2
    exit 1
fi
du -sh "$DIST"
echo "Tesseract pronto em $DIST"
