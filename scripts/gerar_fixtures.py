"""Gera os PDFs sintéticos de teste em uma pasta à escolha.

Todos os documentos produzidos são fictícios. Serve para validar a ferramenta
sem utilizar qualquer processo judicial real.

Uso:
    python scripts/gerar_fixtures.py C:\\temp\\fixtures_anonimizador
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from tests.fixtures.gerador import gerar_todas  # noqa: E402


def main() -> int:
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "fixtures_geradas"
    criadas = gerar_todas(destino)
    print(f"{len(criadas)} documento(s) sintético(s) gerado(s) em: {destino}")
    for nome in sorted(criadas):
        print(f"  - {nome}")
    print(
        "\nEstes arquivos contêm apenas dados fictícios e destinam-se à validação "
        "da ferramenta antes de qualquer uso profissional."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
