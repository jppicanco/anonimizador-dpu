# -*- mode: python ; coding: utf-8 -*-
"""Especificação do PyInstaller para gerar o aplicativo de Mac.

Equivale a ``scripts/anonimizador_dpu.spec`` (Windows), com três diferenças:

* gera um pacote ``Anonimizador DPU.app``, o formato de aplicativo do macOS;
* embute o Tesseract compilado por ``scripts/mac/construir_tesseract.sh``
  (pasta ``tesseract/`` na raiz), de modo que o colega não precisa instalar
  nada;
* leva só a tradução do Qt para o português (botões "Sim"/"Não" e o menu do
  aplicativo), descartando as dos demais idiomas.

Uso (a partir da raiz do projeto): ``scripts/mac/gerar_app.sh``, ou

    .venv/bin/python -m PyInstaller scripts/mac/anonimizador_dpu_mac.spec --noconfirm

O resultado fica em ``dist/Anonimizador DPU.app``.
"""

import re
from pathlib import Path

RAIZ = Path(SPECPATH).parent.parent  # noqa: F821 - SPECPATH é injetado pelo PyInstaller
TESSERACT = RAIZ / "tesseract"
ICONE = RAIZ / ".build" / "icone" / "AnonimizadorDPU.icns"

if not (TESSERACT / "tesseract").is_file():
    raise SystemExit(
        "Tesseract embutido não encontrado em tesseract/. Rode antes:\n"
        "    scripts/mac/construir_tesseract.sh"
    )

_config = (RAIZ / "anonimizador_dpu" / "core" / "config.py").read_text(encoding="utf-8")
VERSAO = re.search(r'^APP_VERSAO = "([^"]+)"', _config, re.M).group(1)

#: Versão mínima do macOS. Quem manda é o PySide6 6.11.3 (binários para macOS
#: 15); o Tesseract embutido aceita macOS 12. Declarada no Info.plist, faz o
#: Finder recusar a abertura com mensagem clara em sistema mais antigo, em vez
#: de o aplicativo simplesmente não abrir.
MACOS_MINIMO = "15.0"

a = Analysis(  # noqa: F821
    [str(RAIZ / "scripts" / "mac" / "executavel_mac.py")],
    pathex=[str(RAIZ)],
    binaries=[(str(TESSERACT / "tesseract"), "tesseract")],
    datas=[
        (str(TESSERACT / "tessdata"), "tesseract/tessdata"),
        (str(TESSERACT / "licencas"), "tesseract/licencas"),
    ],
    hiddenimports=[
        "anonimizador_dpu.app.main",
        "anonimizador_dpu.app.ui.main_window",
        "anonimizador_dpu.app.ui.review_panel",
        "anonimizador_dpu.app.ui.page_viewer",
        "anonimizador_dpu.app.ui.workers",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Mesma lista do executável Windows (ver o comentário sobre o spaCy lá).
    excludes=[
        "tkinter",
        "matplotlib",
        "pytest",
        "spacy",
        "thinc",
        "torch",
        "transformers",
        "bitsandbytes",
        "presidio_analyzer",
        "cv2",
        "scipy",
        "pyarrow",
        "pandas",
        "llvmlite",
        "numba",
        "onnxruntime",
        "av",
        "IPython",
        "notebook",
        "setuptools",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtQuick",
        "PySide6.QtQml",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtMultimedia",
        "PySide6.QtNetwork",
    ],
    noarchive=False,
)


# ---------------------------------------------------------------------------
# Redução do pacote. No Mac os módulos do Qt são "frameworks" (QtWebEngineCore
# .framework…), e não DLLs "qt6…" como no Windows; por isso a lista é própria.
# Lista NEGATIVA, pelo mesmo motivo do spec Windows: esquecer uma dependência
# interna numa lista positiva impede o aplicativo de abrir.
# ---------------------------------------------------------------------------
FRAMEWORKS_DESCARTAVEIS = (
    "qtwebengine",
    "qtwebview",
    "qtwebsockets",
    "qtwebchannel",
    "qtquick",
    "qtqml",
    "qt3d",
    "qtmultimedia",
    "qtcharts",
    "qtdatavisualization",
    "qtgraphs",
    "qtpdf",
    "qtdesigner",
    "qttest",
    "qtsql",
    "qtbluetooth",
    "qtnfc",
    "qtpositioning",
    "qtlocation",
    "qtsensors",
    "qtserialport",
    "qtserialbus",
    "qtremoteobjects",
    "qtscxml",
    "qtstatemachine",
    "qttexttospeech",
    "qthelp",
    "qtuitools",
    "qtspatialaudio",
    "qtvirtualkeyboard",
    "qtshadertools",
    "qtnetwork",
)

PASTAS_DESCARTAVEIS = (
    "/qml/",
    "/typesystems/",
    "/glue/",
    "/include/",
    "/examples/",
    "/qtwebengine",
)

#: Únicas traduções do Qt mantidas (as demais somam cerca de 15 MB).
TRADUCOES_MANTIDAS = ("qtbase_pt_br.qm", "qt_pt_br.qm")


def _manter(destino: str) -> bool:
    caminho = str(destino).replace("\\", "/").lower()
    if "pyside6" not in caminho and "shiboken6" not in caminho:
        return True
    if any(p in caminho for p in PASTAS_DESCARTAVEIS):
        return False
    if "/translations/" in caminho:
        return caminho.rsplit("/", 1)[-1] in TRADUCOES_MANTIDAS
    partes = caminho.split("/")
    for parte in partes:
        nome = parte.removesuffix(".framework")
        if nome.startswith(FRAMEWORKS_DESCARTAVEIS):
            return False
    base = partes[-1]
    # Módulos Python do PySide6 correspondentes (QtWebEngineCore.abi3.so…).
    return not base.startswith(FRAMEWORKS_DESCARTAVEIS)


def _manter_entrada(entrada) -> bool:
    destino, origem, tipo = entrada
    if not _manter(destino):
        return False
    # No Mac, o PyInstaller cria atalhos na raiz (ex.: "QtNetwork" ->
    # PySide6/Qt/lib/QtNetwork.framework/…). Se o framework foi descartado, o
    # atalho ficaria apontando para o nada.
    return tipo != "SYMLINK" or _manter(origem)


a.binaries = [x for x in a.binaries if _manter_entrada(x)]
a.datas = [x for x in a.datas if _manter_entrada(x)]

pyz = PYZ(a.pure)  # noqa: F821

exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AnonimizadorDPU",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # aplicação gráfica
    argv_emulation=False,
    target_arch="arm64",
    codesign_identity=None,  # assinatura local (ad hoc); não há certificado da Apple
    entitlements_file=None,
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnonimizadorDPU",
)

app = BUNDLE(  # noqa: F821
    coll,
    name="Anonimizador DPU.app",
    icon=str(ICONE) if ICONE.exists() else None,
    bundle_identifier="br.def.dpu.anonimizador",
    version=VERSAO,
    info_plist={
        "CFBundleName": "Anonimizador DPU",
        "CFBundleDisplayName": "Anonimizador DPU",
        "CFBundleShortVersionString": VERSAO,
        "CFBundleVersion": VERSAO,
        # Faz o macOS exibir em português os painéis do próprio sistema
        # (escolha de arquivos e pastas), mesmo sem pastas .lproj.
        "CFBundleDevelopmentRegion": "pt_BR",
        "CFBundleLocalizations": ["pt_BR", "pt"],
        "CFBundleAllowMixedLocalizations": True,
        "LSMinimumSystemVersion": MACOS_MINIMO,
        "LSArchitecturePriority": ["arm64"],
        "LSApplicationCategoryType": "public.app-category.productivity",
        "NSHighResolutionCapable": True,
        "NSRequiresAquaSystemAppearance": False,
        "NSHumanReadableCopyright": "Código aberto sob a licença AGPL-3.0 ou posterior.",
    },
)
