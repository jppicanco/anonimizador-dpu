"""Gera o ícone do aplicativo de Mac (.icns) sem depender de arquivos externos.

Desenho neutro — uma folha com linhas de texto, algumas cobertas por tarjas —,
sem brasão nem logotipo institucional. A versão Windows usa o ícone padrão do
PyInstaller; no Mac, o ícone aparece no Dock e no Finder, e o padrão confunde.

Uso: .venv/bin/python scripts/mac/gerar_icone.py <destino.icns>
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

AZUL = (21, 101, 192, 255)  # mesma cor do botão principal (ui/tema.py)
AZUL_ESCURO = (13, 71, 161, 255)
BRANCO = (255, 255, 255, 255)
CINZA = (176, 186, 199, 255)
PRETO = (20, 20, 20, 255)


def desenhar(lado: int = 1024) -> Image.Image:
    escala = lado / 1024
    img = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    def r(*valores: float) -> list[int]:
        return [round(v * escala) for v in valores]

    # Fundo no formato e na margem dos ícones do macOS (824 px de 1024).
    d.rounded_rectangle(r(100, 100, 924, 924), radius=round(185 * escala), fill=AZUL)
    d.rounded_rectangle(r(100, 520, 924, 924), radius=round(185 * escala), fill=AZUL_ESCURO)
    d.rectangle(r(100, 520, 924, 700), fill=AZUL_ESCURO)
    d.rectangle(r(100, 520, 924, 560), fill=AZUL)

    # Folha com canto dobrado.
    d.polygon(
        [tuple(r(300, 210)), tuple(r(640, 210)), tuple(r(724, 294)),
         tuple(r(724, 814)), tuple(r(300, 814))],
        fill=BRANCO,
    )
    d.polygon([tuple(r(640, 210)), tuple(r(640, 294)), tuple(r(724, 294))], fill=CINZA)

    # Linhas de texto; algumas tarjadas.
    linhas = [
        (360, 330, 600, CINZA), (360, 395, 664, PRETO), (360, 460, 664, CINZA),
        (360, 525, 520, CINZA), (540, 525, 664, PRETO), (360, 590, 664, CINZA),
        (360, 655, 600, PRETO), (360, 720, 560, CINZA),
    ]
    for x0, y, x1, cor in linhas:
        altura = 30 if cor == PRETO else 18
        d.rounded_rectangle(
            r(x0, y - altura / 2, x1, y + altura / 2), radius=round(6 * escala), fill=cor
        )
    return img


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    destino = Path(sys.argv[1])
    destino.parent.mkdir(parents=True, exist_ok=True)
    base = desenhar(1024)
    with tempfile.TemporaryDirectory() as tmp:
        conjunto = Path(tmp) / "icone.iconset"
        conjunto.mkdir()
        for tamanho in (16, 32, 128, 256, 512):
            for fator in (1, 2):
                lado = tamanho * fator
                nome = f"icon_{tamanho}x{tamanho}{'@2x' if fator == 2 else ''}.png"
                base.resize((lado, lado), Image.Resampling.LANCZOS).save(conjunto / nome)
        subprocess.run(
            ["iconutil", "--convert", "icns", str(conjunto), "--output", str(destino)],
            check=True,
        )
        base.save(destino.with_suffix(".png"))
    print(f"ícone gerado: {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
