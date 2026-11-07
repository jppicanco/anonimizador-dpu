"""Verifica se a máquina tem tudo o que o Anonimizador DPU precisa.

Executa somente verificações locais. Não baixa nem instala nada: instalação e
processamento são operações separadas por decisão de projeto.

Uso:
    python scripts/verificar_ambiente.py
"""

from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

DEPENDENCIAS = [
    ("fitz", "PyMuPDF"),
    ("pytesseract", "pytesseract"),
    ("PIL", "Pillow"),
    ("numpy", "numpy"),
    ("PySide6", "PySide6"),
]


def _marca(ok: bool) -> str:
    return "[ OK ]" if ok else "[FALHA]"


def main() -> int:
    print("Anonimizador DPU — verificação de ambiente")
    print("=" * 58)
    print(f"Python: {sys.version.split()[0]}  ({sys.executable})")
    print(f"Sistema: {platform.system()} {platform.release()} {platform.machine()}")
    print("-" * 58)

    problemas = 0

    if sys.version_info < (3, 11):
        print(f"{_marca(False)} Python 3.11 ou superior é exigido.")
        problemas += 1
    else:
        print(f"{_marca(True)} Versão do Python compatível.")

    for modulo, nome in DEPENDENCIAS:
        try:
            mod = importlib.import_module(modulo)
            versao = getattr(mod, "__version__", "")
            if modulo == "fitz":
                versao = mod.version[0]
            print(f"{_marca(True)} {nome} {versao}")
        except Exception as exc:
            print(f"{_marca(False)} {nome} indisponível: {exc}")
            problemas += 1

    from anonimizador_dpu.core.config import Config
    from anonimizador_dpu.core.ocr_engine import verificar_ocr

    cfg = Config.carregar()
    status = verificar_ocr(cfg.ocr)
    if status.disponivel:
        print(f"{_marca(True)} Tesseract {status.versao} em {status.caminho}")
        print(f"        Idiomas instalados: {', '.join(sorted(status.idiomas))}")
    else:
        print(f"{_marca(False)} OCR local indisponível: {status.erro}")
        print(
            "        Instale o Tesseract OCR e o arquivo por.traineddata. "
            "Sem OCR, páginas digitalizadas não podem ser examinadas e o "
            "documento nunca será aprovado nos testes automatizados."
        )
        problemas += 1

    print("-" * 58)
    if problemas:
        print(f"{problemas} pendência(s) encontrada(s). Consulte o README.md.")
        return 1
    print("Ambiente pronto para uso.")
    print(
        "Lembre-se: a aprovação automatizada não garante anonimização integral "
        "e não substitui a revisão humana."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
