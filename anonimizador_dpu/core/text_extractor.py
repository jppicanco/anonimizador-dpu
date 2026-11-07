"""Extração do texto selecionável do PDF, com mapa de posições.

O texto de cada página é linearizado a partir das palavras retornadas pelo
PyMuPDF. Cada palavra guarda o intervalo que ocupa no texto linearizado e a sua
posição geométrica na página, o que permite mapear qualquer ocorrência
detectada de volta para coordenadas exatas, sem depender de busca textual
posterior (frágil diante de quebras de linha e hifenização).
"""

from __future__ import annotations

import fitz

from .models import PaginaTexto, PalavraPos

#: Chaves de metadados padrão de PDF examinadas em busca de dados pessoais.
CHAVES_METADADOS = (
    "title",
    "author",
    "subject",
    "keywords",
    "creator",
    "producer",
)


def linearizar_palavras(palavras: list[tuple]) -> tuple[str, list[PalavraPos]]:
    """Converte a lista de palavras do PyMuPDF em texto + mapa de posições.

    Espera tuplas no formato ``(x0, y0, x1, y1, texto, bloco, linha, palavra)``.
    """
    partes: list[str] = []
    posicoes: list[PalavraPos] = []
    cursor = 0
    ultima_linha: tuple[int, int] | None = None

    for p in sorted(palavras, key=lambda w: (w[5], w[6], w[7])):
        x0, y0, x1, y1, texto = p[0], p[1], p[2], p[3], p[4]
        linha = (p[5], p[6])
        if ultima_linha is None:
            separador = ""
        elif linha != ultima_linha:
            separador = "\n"
        else:
            separador = " "
        if separador:
            partes.append(separador)
            cursor += len(separador)
        inicio = cursor
        partes.append(texto)
        cursor += len(texto)
        posicoes.append(
            PalavraPos(texto=texto, bbox=(x0, y0, x1, y1), inicio=inicio, fim=cursor)
        )
        ultima_linha = linha

    return "".join(partes), posicoes


def extrair_pagina(page: fitz.Page) -> PaginaTexto:
    """Extrai o texto selecionável de uma página com o mapa de posições."""
    resultado = PaginaTexto(numero=page.number)
    try:
        palavras = page.get_text("words") or []
    except Exception as exc:  # pragma: no cover - página corrompida
        resultado.observacao = f"Falha ao extrair texto: {exc}"[:200]
        return resultado
    texto, posicoes = linearizar_palavras(palavras)
    resultado.texto_pdf = texto
    resultado.palavras_pdf = posicoes
    resultado.examinada = bool(texto.strip())
    return resultado


def bboxes_para_intervalo(
    palavras: list[PalavraPos], inicio: int, fim: int
) -> list[tuple[float, float, float, float]]:
    """Devolve as áreas das palavras que cobrem o intervalo [inicio, fim).

    Palavras contíguas na mesma linha são unidas em um único retângulo, para que
    a redação não fique fragmentada.
    """
    selecionadas = [p for p in palavras if p.inicio < fim and p.fim > inicio]
    if not selecionadas:
        return []
    caixas: list[list[float]] = []
    for palavra in selecionadas:
        x0, y0, x1, y1 = palavra.bbox
        if caixas:
            ax0, ay0, ax1, ay1 = caixas[-1]
            mesma_linha = abs(ay0 - y0) < max(1.0, (ay1 - ay0) * 0.5)
            proxima = x0 - ax1 < max(6.0, (ay1 - ay0))
            if mesma_linha and proxima:
                caixas[-1] = [min(ax0, x0), min(ay0, y0), max(ax1, x1), max(ay1, y1)]
                continue
        caixas.append([x0, y0, x1, y1])
    return [tuple(c) for c in caixas]  # type: ignore[misc]


def textos_de_anotacoes(page: fitz.Page) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Conteúdo textual das anotações da página (comentários, notas, marcações)."""
    saida: list[tuple[str, tuple[float, float, float, float]]] = []
    try:
        anotacoes = list(page.annots() or [])
    except Exception:  # pragma: no cover
        return saida
    for annot in anotacoes:
        try:
            info = annot.info or {}
            partes = [info.get("content", ""), info.get("title", ""), info.get("subject", "")]
            texto = " ".join(x for x in partes if x).strip()
            if texto:
                r = annot.rect
                saida.append((texto, (r.x0, r.y0, r.x1, r.y1)))
        except Exception:  # pragma: no cover
            continue
    return saida


def textos_de_formulario(page: fitz.Page) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Valores e nomes dos campos de formulário da página."""
    saida: list[tuple[str, tuple[float, float, float, float]]] = []
    try:
        widgets = list(page.widgets() or [])
    except Exception:  # pragma: no cover
        return saida
    for w in widgets:
        try:
            valor = str(w.field_value or "").strip()
            nome = str(w.field_name or "").strip()
            texto = " ".join(x for x in (valor, nome) if x)
            if texto:
                r = w.rect
                saida.append((texto, (r.x0, r.y0, r.x1, r.y1)))
        except Exception:  # pragma: no cover
            continue
    return saida


def textos_de_links(page: fitz.Page) -> list[tuple[str, tuple[float, float, float, float]]]:
    """URIs presentes nos links da página."""
    saida: list[tuple[str, tuple[float, float, float, float]]] = []
    try:
        links = page.get_links() or []
    except Exception:  # pragma: no cover
        return saida
    for link in links:
        uri = link.get("uri") or link.get("file") or ""
        if uri:
            r = fitz.Rect(link.get("from", (0, 0, 0, 0)))
            saida.append((str(uri), (r.x0, r.y0, r.x1, r.y1)))
    return saida


def metadados_textuais(doc: fitz.Document) -> dict[str, str]:
    """Metadados padrão com conteúdo, prontos para análise de dados pessoais."""
    meta = doc.metadata or {}
    return {k: str(v) for k, v in meta.items() if k in CHAVES_METADADOS and v}
