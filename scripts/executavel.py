"""Ponto de entrada do executável Windows.

O PyInstaller executa o script inicial como ``__main__``, sem pacote pai, de
modo que os imports relativos de ``anonimizador_dpu/app/main.py`` não funcionam
quando aquele arquivo é usado diretamente como ponto de entrada. Este módulo
resolve isso importando o pacote pelo nome absoluto.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Em execução a partir do código-fonte, garante que a raiz do projeto esteja no
# caminho de importação. No executável empacotado, o pacote já está embutido.
_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

from anonimizador_dpu.app.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
