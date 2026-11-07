# -*- mode: python ; coding: utf-8 -*-
"""Especificação do PyInstaller para gerar o executável Windows.

Uso (a partir da raiz do projeto, com o ambiente virtual ativado):

    pip install pyinstaller
    pyinstaller scripts/anonimizador_dpu.spec --noconfirm

O executável resultante fica em ``dist/AnonimizadorDPU/``.

Observação importante: o executável NÃO embute o Tesseract OCR. O binário do
Tesseract e os dados de idioma (por.traineddata) continuam sendo instalados
separadamente na máquina, por decisão de projeto — instalação e processamento
documental são operações distintas, e o aplicativo nunca baixa componentes
durante o uso.
"""

from pathlib import Path

RAIZ = Path(SPECPATH).parent  # noqa: F821 - SPECPATH é injetado pelo PyInstaller

a = Analysis(  # noqa: F821
    # O ponto de entrada é scripts/executavel.py, e não app/main.py: o
    # PyInstaller roda o script inicial como "__main__", sem pacote pai, e os
    # imports relativos de app/main.py falhariam.
    [str(RAIZ / "scripts" / "executavel.py")],
    pathex=[str(RAIZ)],
    binaries=[],
    datas=[],
    hiddenimports=[
        "anonimizador_dpu.app.main",
        "anonimizador_dpu.app.ui.main_window",
        "anonimizador_dpu.app.ui.review_panel",
        "anonimizador_dpu.app.ui.page_viewer",
        "anonimizador_dpu.app.ui.workers",
    ],
    hookspath=[],
    runtime_hooks=[],
    # Módulos pesados e desnecessários para a aplicação; reduzem o tamanho do
    # pacote e a superfície de ataque.
    #
    # Nota sobre `spacy`: o reconhecimento de entidades por modelo local é
    # opcional e está protegido por try/except em core/entity_detector.py. Como
    # a análise estática do PyInstaller enxerga esse import, ele arrastaria
    # spacy, thinc, torch, transformers e dependências correlatas — mais de 1 GB.
    # O executável é distribuído sem esse recurso; quem precisar dele deve
    # executar a aplicação a partir do código-fonte, com o modelo instalado
    # localmente.
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
    ],
    noarchive=False,
)


# ---------------------------------------------------------------------------
# Redução do pacote: o PySide6 traz todo o Qt (vídeo, 3D, WebEngine, QML…).
# A aplicação usa apenas QtCore, QtGui e QtWidgets. Sem este filtro, a pasta
# distribuída passa de 1,4 GB.
# ---------------------------------------------------------------------------
# Lista NEGATIVA explícita: remove apenas módulos Qt que a aplicação
# comprovadamente não usa. Uma lista positiva é perigosa — basta esquecer uma
# dependência interna (como pyside6.abi3.dll) para o executável deixar de abrir.
MODULOS_QT_DESCARTAVEIS = (
    "qt6webengine",
    "qt6webview",
    "qt6websockets",
    "qt6webchannel",
    "qt6quick",
    "qt6qml",
    "qt63d",
    "qt6multimedia",
    "qt6charts",
    "qt6datavisualization",
    "qt6graphs",
    "qt6pdf",
    "qt6designer",
    "qt6test",
    "qt6sql",
    "qt6bluetooth",
    "qt6nfc",
    "qt6positioning",
    "qt6location",
    "qt6sensors",
    "qt6serialport",
    "qt6serialbus",
    "qt6remoteobjects",
    "qt6scxml",
    "qt6statemachine",
    "qt6texttospeech",
    "qt6help",
    "qt6uitools",
    "qt6spatialaudio",
    "qt6virtualkeyboard",
    "qt6quick3d",
    "qt6shadertools",
)

#: Diretórios do PySide6 sem utilidade para esta aplicação.
PASTAS_DESCARTAVEIS = (
    "/qml/",
    "/translations/",
    "/typesystems/",
    "/glue/",
    "/include/",
    "/examples/",
    "/qtwebengine",
)


def _manter(destino: str) -> bool:
    caminho = str(destino).replace("\\", "/").lower()
    if "pyside6" not in caminho and "shiboken6" not in caminho:
        return True
    if any(p in caminho for p in PASTAS_DESCARTAVEIS):
        return False
    base = caminho.rsplit("/", 1)[-1]
    return not base.startswith(MODULOS_QT_DESCARTAVEIS)


a.binaries = TOC([x for x in a.binaries if _manter(x[0])])  # noqa: F821
a.datas = TOC([x for x in a.datas if _manter(x[0])])  # noqa: F821

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
    console=False,  # aplicação gráfica: sem janela de console
)

coll = COLLECT(  # noqa: F821
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="AnonimizadorDPU",
)
