"""OCR local com Tesseract.

Nenhum serviço remoto é utilizado. O binário do Tesseract e os dados de idioma
(``por.traineddata``) precisam estar instalados previamente na máquina; o
aplicativo nunca faz download de componentes durante o processamento.

O OCR devolve, além do texto, a posição de cada palavra convertida para
coordenadas de página do PDF, o que permite redigir áreas de imagem com
precisão. Quando a confiança do reconhecimento é baixa, a página é marcada como
exigindo inspeção — o retorno de algum texto nunca é tratado como prova de que
a página foi integralmente examinada.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import fitz

from .audit_logger import obter_logger
from .config import ConfigOCR
from .models import PaginaTexto, PalavraPos

_log = obter_logger("ocr")

try:  # pragma: no cover - dependência externa opcional em tempo de import
    import pytesseract
    from PIL import Image

    _IMPORT_OK = True
    _ERRO_IMPORT = ""
except Exception as exc:  # pragma: no cover
    pytesseract = None  # type: ignore[assignment]
    Image = None  # type: ignore[assignment]
    _IMPORT_OK = False
    _ERRO_IMPORT = str(exc)


@dataclass
class StatusOCR:
    disponivel: bool
    versao: str = ""
    idiomas: tuple[str, ...] = ()
    caminho: str = ""
    erro: str = ""


def _configurar_binario(cfg: ConfigOCR) -> str:
    caminho = cfg.caminho_tesseract or shutil.which("tesseract") or ""
    if caminho and pytesseract is not None:
        pytesseract.pytesseract.tesseract_cmd = caminho
        # Os dados de idioma ficam ao lado do binário. Apontar explicitamente
        # evita depender de registro do Windows ou de variável de ambiente, o
        # que é o caso do Tesseract embutido no pacote distribuído.
        tessdata = Path(cfg.tessdata) if cfg.tessdata else Path(caminho).parent / "tessdata"
        if tessdata.is_dir():
            os.environ["TESSDATA_PREFIX"] = str(tessdata)
    return caminho


def verificar_ocr(cfg: ConfigOCR | None = None) -> StatusOCR:
    """Verifica a disponibilidade real do Tesseract e dos idiomas instalados."""
    cfg = cfg or ConfigOCR()
    if not _IMPORT_OK:
        return StatusOCR(False, erro=f"pytesseract/Pillow indisponível: {_ERRO_IMPORT}")
    caminho = _configurar_binario(cfg)
    if not caminho or not Path(caminho).exists():
        return StatusOCR(
            False,
            erro="Executável do Tesseract não encontrado. Instale o Tesseract OCR e "
            "informe o caminho na configuração.",
        )
    try:
        versao = str(pytesseract.get_tesseract_version())
        idiomas = tuple(pytesseract.get_languages(config=""))
    except Exception as exc:
        return StatusOCR(False, caminho=caminho, erro=f"Tesseract não respondeu: {exc}")
    faltantes = [i for i in cfg.idiomas.split("+") if i and i not in idiomas]
    if faltantes:
        return StatusOCR(
            False,
            versao=versao,
            idiomas=idiomas,
            caminho=caminho,
            erro="Dados de idioma ausentes: " + ", ".join(faltantes),
        )
    return StatusOCR(True, versao=versao, idiomas=idiomas, caminho=caminho)


def renderizar_pagina(page: fitz.Page, dpi: int, max_px: int = 10000):
    """Renderiza a página como imagem PIL, respeitando um limite de dimensão."""
    zoom = max(dpi, 72) / 72.0
    largura = page.rect.width * zoom
    altura = page.rect.height * zoom
    if max(largura, altura) > max_px:
        zoom *= max_px / max(largura, altura)
    matriz = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matriz, alpha=False)
    imagem = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    return imagem, zoom


def _px_para_pontos(
    x: float, y: float, w: float, h: float, page: fitz.Page, zoom: float
) -> tuple[float, float, float, float]:
    """Converte uma caixa em pixels da imagem renderizada para pontos da página."""
    x0 = page.rect.x0 + x / zoom
    y0 = page.rect.y0 + y / zoom
    x1 = page.rect.x0 + (x + w) / zoom
    y1 = page.rect.y0 + (y + h) / zoom
    return (x0, y0, x1, y1)


def ocr_pagina(page: fitz.Page, cfg: ConfigOCR, max_px: int = 10000) -> PaginaTexto:
    """Executa OCR local em uma página e devolve texto + posições das palavras."""
    resultado = PaginaTexto(numero=page.number)
    status = verificar_ocr(cfg)
    if not status.disponivel:
        resultado.ocr_falhou = True
        resultado.ocr_erro = status.erro
        return resultado

    try:
        imagem, zoom = renderizar_pagina(page, cfg.dpi, max_px)
    except Exception as exc:
        resultado.ocr_falhou = True
        resultado.ocr_erro = f"Falha ao renderizar a página: {exc}"[:200]
        return resultado

    try:
        dados = pytesseract.image_to_data(
            imagem,
            lang=cfg.idiomas,
            config=f"--psm {cfg.psm}",
            output_type=pytesseract.Output.DICT,
            timeout=cfg.timeout_pagina_s,
        )
    except Exception as exc:
        resultado.ocr_falhou = True
        resultado.ocr_erro = f"Falha no OCR: {exc}"[:200]
        return resultado
    finally:
        try:
            imagem.close()
        except Exception:  # pragma: no cover
            pass

    partes: list[str] = []
    posicoes: list[PalavraPos] = []
    cursor = 0
    chave_linha: tuple[int, int, int, int] | None = None
    confiancas: list[float] = []
    aceitas = 0

    total = len(dados.get("text", []))
    for i in range(total):
        texto = (dados["text"][i] or "").strip()
        if not texto:
            continue
        try:
            conf = float(dados["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        confiancas.append(conf)
        if conf >= cfg.confianca_minima_palavra:
            aceitas += 1
        linha = (
            dados["page_num"][i],
            dados["block_num"][i],
            dados["par_num"][i],
            dados["line_num"][i],
        )
        separador = "" if chave_linha is None else ("\n" if linha != chave_linha else " ")
        if separador:
            partes.append(separador)
            cursor += len(separador)
        inicio = cursor
        partes.append(texto)
        cursor += len(texto)
        bbox = _px_para_pontos(
            float(dados["left"][i]),
            float(dados["top"][i]),
            float(dados["width"][i]),
            float(dados["height"][i]),
            page,
            zoom,
        )
        posicoes.append(
            PalavraPos(texto=texto, bbox=bbox, inicio=inicio, fim=cursor, confianca=conf)
        )
        chave_linha = linha

    resultado.texto_ocr = "".join(partes)
    resultado.palavras_ocr = posicoes
    resultado.ocr_executado = True
    resultado.ocr_confianca_media = (sum(confiancas) / len(confiancas)) if confiancas else 0.0
    resultado.ocr_cobertura = (aceitas / len(confiancas)) if confiancas else 0.0
    resultado.examinada = resultado.ocr_cobertura >= cfg.cobertura_minima and bool(posicoes)
    if not resultado.examinada:
        resultado.observacao = (
            "Cobertura de OCR insuficiente: a página não pode ser considerada "
            "integralmente examinada."
        )
    return resultado


def descrever_ambiente_ocr(cfg: ConfigOCR | None = None) -> str:
    """Texto curto sobre o estado do OCR, para exibição na interface."""
    status = verificar_ocr(cfg)
    if status.disponivel:
        return (
            f"Tesseract {status.versao} em {status.caminho} — idiomas: "
            + ", ".join(sorted(status.idiomas))
        )
    return f"OCR indisponível: {status.erro}"
