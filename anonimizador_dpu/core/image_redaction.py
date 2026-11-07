"""Apoio à redação em páginas digitalizadas e reconstrução de páginas.

Duas operações distintas:

* **conferência de área** — após a redação, a região é renderizada novamente e
  verificada: se ainda apresentar variação de pixels compatível com conteúdo,
  a redação é considerada suspeita e a página não pode ser aprovada;
* **reconstrução (rasterização)** — quando a estrutura interna de uma página
  não pode ser limpa com segurança, a página é substituída pela sua própria
  renderização. A reconstrução elimina camadas, texto oculto e objetos
  residuais, mas também elimina texto selecionável, links e formulários, e
  **não** é automaticamente segura: o resultado continua sendo validado.
"""

from __future__ import annotations

import fitz

from .audit_logger import obter_logger

_log = obter_logger("imagem")


def area_contem_conteudo(
    page: fitz.Page, bbox: tuple[float, float, float, float], tolerancia: int = 12
) -> bool:
    """Indica se a região renderizada ainda apresenta variação de pixels.

    Uma área efetivamente redigida fica preenchida por uma cor uniforme (ou com
    o pseudônimo escrito por cima). Variação alta sugere que o conteúdo original
    permaneceu visível.
    """
    rect = fitz.Rect(bbox) & page.rect
    if rect.is_empty or rect.width < 1 or rect.height < 1:
        return False
    try:
        pix = page.get_pixmap(clip=rect, dpi=120, alpha=False)
    except Exception as exc:  # pragma: no cover
        _log.warning("Falha ao renderizar área para conferência: %s", exc)
        return True  # na dúvida, trata como não conferida
    amostras = pix.samples
    if not amostras:
        return False
    valores = list(amostras)
    minimo, maximo = min(valores), max(valores)
    return (maximo - minimo) > tolerancia


def cobertura_de_cor(
    page: fitz.Page, bbox: tuple[float, float, float, float], cor: tuple[float, float, float]
) -> float:
    """Fração aproximada da área preenchida com a cor de redação informada."""
    rect = fitz.Rect(bbox) & page.rect
    if rect.is_empty:
        return 0.0
    try:
        pix = page.get_pixmap(clip=rect, dpi=100, alpha=False)
    except Exception:  # pragma: no cover
        return 0.0
    alvo = tuple(int(round(c * 255)) for c in cor)
    dados = pix.samples
    total = pix.width * pix.height
    if total == 0:
        return 0.0
    iguais = 0
    passo = 3
    for i in range(0, len(dados) - 2, passo):
        if (
            abs(dados[i] - alvo[0]) <= 24
            and abs(dados[i + 1] - alvo[1]) <= 24
            and abs(dados[i + 2] - alvo[2]) <= 24
        ):
            iguais += 1
    return iguais / total


def rasterizar_documento(
    doc: fitz.Document, paginas: set[int], dpi: int = 200
) -> fitz.Document:
    """Devolve um novo documento com as páginas indicadas substituídas por imagem.

    As demais páginas são copiadas sem alteração.
    """
    novo = fitz.open()
    for pagina in doc:
        if pagina.number in paginas:
            pix = pagina.get_pixmap(dpi=dpi, alpha=False)
            destino = novo.new_page(width=pagina.rect.width, height=pagina.rect.height)
            destino.insert_image(destino.rect, pixmap=pix)
        else:
            novo.insert_pdf(doc, from_page=pagina.number, to_page=pagina.number)
    return novo


def imagens_da_pagina(page: fitz.Page) -> list[tuple[int, fitz.Rect]]:
    """Lista (xref, área) das imagens posicionadas na página."""
    saida: list[tuple[int, fitz.Rect]] = []
    try:
        for info in page.get_image_info(xrefs=True):
            xref = int(info.get("xref", 0))
            saida.append((xref, fitz.Rect(info.get("bbox", (0, 0, 0, 0)))))
    except Exception:  # pragma: no cover
        pass
    return saida


def regiao_de_assinatura_provavel(page: fitz.Page) -> list[fitz.Rect]:
    """Heurística simples para localizar imagens pequenas que podem ser assinaturas.

    Serve apenas para sugerir áreas na revisão humana; não decide nada sozinha.
    """
    sugestoes: list[fitz.Rect] = []
    area_pagina = abs(page.rect.get_area()) or 1.0
    for _, rect in imagens_da_pagina(page):
        area = abs(rect.get_area())
        if area <= 0:
            continue
        proporcao = area / area_pagina
        largura, altura = rect.width, rect.height
        if 0.002 < proporcao < 0.12 and altura > 0 and 1.2 < (largura / altura) < 8.0:
            sugestoes.append(rect)
    return sugestoes
