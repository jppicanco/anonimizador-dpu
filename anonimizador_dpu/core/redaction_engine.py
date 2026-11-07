"""Redação efetiva do conteúdo identificado.

A redação remove o conteúdo original: o texto é eliminado do fluxo de conteúdo
da página e os pixels correspondentes nas imagens são substituídos. Não se
trata de sobreposição de retângulos.

Garantias e limites implementados aqui:

* o arquivo original nunca é aberto para escrita; trabalha-se sobre uma cópia;
* ocorrência confirmada sem área determinada com segurança **não** é redigida
  "no palpite": ela é marcada como falha e bloqueia a aprovação da página;
* páginas cuja estrutura não pode ser limpa podem ser reconstruídas a partir da
  renderização, o que é registrado no relatório com as perdas correspondentes;
* após salvar, o documento é reaberto para conferência das áreas redigidas.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

import fitz

from .attachment_inspector import listar_anexos, riscos_de_anexos
from .audit_logger import obter_logger
from .config import Config
from .image_redaction import area_contem_conteudo, rasterizar_documento
from .metadata_cleaner import higienizar, limpar_documento
from .models import (
    BBox,
    Candidato,
    Origem,
    ResultadoRedacao,
    Risco,
    Severidade,
    Status,
)
from .security import DiretorioTemporarioSeguro, sha256_arquivo

_log = obter_logger("redacao")

Progresso = Callable[[str, int, int], None]
Cancelado = Callable[[], bool]

#: Margem mínima aplicada à área de redação, em pontos.
MARGEM_PADRAO = 1.0


def _retangulo(bbox: BBox, margem: float, limite: fitz.Rect) -> fitz.Rect:
    rect = fitz.Rect(bbox)
    rect = rect + (-margem, -margem, margem, margem)
    rect = rect & limite
    return rect


def _texto_substituto(candidato: Candidato, cfg: Config) -> str | None:
    if cfg.redacao.modo != "pseudonimo":
        return None
    return candidato.pseudonimo or f"[{candidato.categoria.value}]"


def _tamanho_fonte(rect: fitz.Rect, texto: str, cfg: Config) -> float:
    """Calcula um corpo de fonte que caiba na área redigida."""
    if not texto:
        return 0.0
    por_altura = rect.height * 0.70
    por_largura = (rect.width / max(len(texto), 1)) * 1.9
    return max(min(por_altura, por_largura, 11.0), 0.0)


def _marcar_pagina(
    page: fitz.Page, candidatos: list[Candidato], cfg: Config
) -> tuple[int, int, list[Risco]]:
    """Adiciona as anotações de redação de uma página.

    Devolve ``(areas_texto, areas_imagem, riscos)``.
    """
    areas_texto = 0
    areas_imagem = 0
    riscos: list[Risco] = []
    margem = max(cfg.redacao.margem_ocr_pt, MARGEM_PADRAO)

    for candidato in candidatos:
        if not candidato.bboxes:
            candidato.status = Status.FALHA_CRITICA
            candidato.falha = (
                "Ocorrência confirmada sem área determinada com segurança na página. "
                "A redação não foi aplicada."
            )
            riscos.append(
                Risco(
                    "AREA_INDETERMINADA",
                    "Ocorrência confirmada sem coordenadas seguras; página pendente.",
                    Severidade.CRITICO,
                    pagina=page.number,
                    bloqueia_aprovacao=True,
                    detalhe=f"categoria {candidato.categoria.value}, id {candidato.id}",
                )
            )
            continue

        substituto = _texto_substituto(candidato, cfg)
        for bbox in candidato.bboxes:
            rect = _retangulo(bbox, margem, page.rect)
            if rect.is_empty or rect.width < 0.5 or rect.height < 0.5:
                continue
            texto = substituto
            corpo = _tamanho_fonte(rect, texto or "", cfg)
            if texto and corpo < cfg.redacao.tamanho_fonte_min:
                texto = None  # não cabe: aplica tarja sem rótulo
            try:
                page.add_redact_annot(
                    rect,
                    text=texto,
                    fontsize=max(corpo, 1.0) if texto else 11,
                    fill=cfg.redacao.cor_tarja if not texto else (0.0, 0.0, 0.0),
                    text_color=cfg.redacao.cor_texto,
                    cross_out=False,
                )
            except Exception as exc:
                candidato.status = Status.FALHA_CRITICA
                candidato.falha = f"Falha ao marcar área para redação: {exc}"[:200]
                riscos.append(
                    Risco(
                        "FALHA_MARCACAO",
                        "Não foi possível marcar uma área para redação.",
                        Severidade.CRITICO,
                        pagina=page.number,
                        bloqueia_aprovacao=True,
                        detalhe=str(exc)[:200],
                    )
                )
                continue
            if candidato.origem in (Origem.OCR, Origem.TEXTO_E_OCR, Origem.MANUAL):
                areas_imagem += 1
            else:
                areas_texto += 1

    return areas_texto, areas_imagem, riscos


def aplicar_redacoes(
    entrada: Path,
    saida: Path,
    candidatos: list[Candidato],
    cfg: Config,
    paginas_para_reconstruir: set[int] | None = None,
    progresso: Progresso | None = None,
    cancelado: Cancelado | None = None,
) -> ResultadoRedacao:
    """Aplica a redação ao documento e grava o PDF anonimizado.

    ``candidatos`` deve conter apenas ocorrências com status ``CONFIRMADO``.
    """
    resultado = ResultadoRedacao(arquivo_saida=str(saida))
    confirmados = [c for c in candidatos if c.status == Status.CONFIRMADO]
    # Metadado não tem posição em página: sai pela limpeza de metadados, e não
    # pela redação geométrica, que o reprovaria por falta de área.
    de_metadado = [c for c in confirmados if c.origem == Origem.METADADO]
    por_pagina: dict[int, list[Candidato]] = {}
    for candidato in confirmados:
        if candidato.origem != Origem.METADADO:
            por_pagina.setdefault(candidato.pagina, []).append(candidato)

    reconstruir = set(paginas_para_reconstruir or ())

    with DiretorioTemporarioSeguro() as tmp:
        copia = tmp / f"trabalho_{entrada.name}"
        shutil.copy2(entrada, copia)

        try:
            doc = fitz.open(copia)
        except Exception as exc:
            resultado.falhas.append(
                Risco(
                    "ABERTURA_FALHOU",
                    "O documento não pôde ser aberto para redação.",
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                    detalhe=str(exc)[:200],
                )
            )
            return resultado

        with doc:
            if doc.is_encrypted:
                doc.authenticate("")

            anexos = listar_anexos(doc)
            resultado.falhas.extend(
                riscos_de_anexos(anexos, cfg.redacao.remover_anexos)
            )

            total = doc.page_count
            for page in doc:
                if cancelado and cancelado():
                    resultado.cancelado = True
                    return resultado
                if progresso:
                    progresso("Aplicando redação", page.number + 1, total)

                da_pagina = por_pagina.get(page.number, [])
                if da_pagina:
                    t, i, riscos = _marcar_pagina(page, da_pagina, cfg)
                    resultado.redacoes_texto += t
                    resultado.redacoes_imagem += i
                    resultado.falhas.extend(riscos)
                    try:
                        page.apply_redactions(
                            images=fitz.PDF_REDACT_IMAGE_PIXELS,
                            graphics=fitz.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                            text=fitz.PDF_REDACT_TEXT_REMOVE,
                        )
                    except Exception as exc:
                        resultado.falhas.append(
                            Risco(
                                "FALHA_APLICACAO",
                                "Falha ao aplicar a redação na página.",
                                Severidade.CRITICO,
                                pagina=page.number,
                                bloqueia_aprovacao=True,
                                detalhe=str(exc)[:200],
                            )
                        )
                        for candidato in da_pagina:
                            candidato.status = Status.FALHA_CRITICA
                            candidato.falha = "Falha ao aplicar a redação na página."
                        continue
                    for candidato in da_pagina:
                        if candidato.status == Status.CONFIRMADO:
                            candidato.status = Status.REDIGIDO
                            resultado.redacoes_aplicadas += 1

            removidos, estruturas, nao_tratadas = limpar_documento(doc, cfg.redacao)
            resultado.metadados_removidos = removidos
            resultado.estruturas_removidas = estruturas
            resultado.estruturas_nao_tratadas = nao_tratadas
            resultado.estruturas_removidas.extend(higienizar(doc))
            _confirmar_metadados(doc, de_metadado, resultado)

            if reconstruir and cfg.redacao.permitir_rasterizacao:
                try:
                    novo = rasterizar_documento(doc, reconstruir, cfg.redacao.dpi_rasterizacao)
                    with novo:
                        novo.save(saida, garbage=4, deflate=True, clean=True)
                    resultado.paginas_rasterizadas = sorted(reconstruir)
                except Exception as exc:
                    resultado.falhas.append(
                        Risco(
                            "FALHA_RECONSTRUCAO",
                            "Falha ao reconstruir páginas por renderização.",
                            Severidade.CRITICO,
                            bloqueia_aprovacao=True,
                            detalhe=str(exc)[:200],
                        )
                    )
                    return resultado
            else:
                if reconstruir and not cfg.redacao.permitir_rasterizacao:
                    resultado.estruturas_nao_tratadas.append(
                        "páginas que exigiriam reconstrução não foram reconstruídas "
                        "(rasterização desabilitada na configuração)"
                    )
                try:
                    doc.save(saida, garbage=4, deflate=True, clean=True)
                except Exception as exc:
                    resultado.falhas.append(
                        Risco(
                            "FALHA_GRAVACAO",
                            "Falha ao gravar o documento anonimizado.",
                            Severidade.CRITICO,
                            bloqueia_aprovacao=True,
                            detalhe=str(exc)[:200],
                        )
                    )
                    return resultado

    try:
        resultado.sha256_saida = sha256_arquivo(saida)
    except OSError:
        resultado.sha256_saida = ""

    _conferir_areas(saida, confirmados, resultado)
    _log.info(
        "Redação concluída: %d áreas aplicadas (texto=%d, imagem=%d).",
        resultado.redacoes_aplicadas,
        resultado.redacoes_texto,
        resultado.redacoes_imagem,
    )
    return resultado


def _confirmar_metadados(
    doc: fitz.Document, candidatos: list[Candidato], resultado: ResultadoRedacao
) -> None:
    """Dá por redigida a ocorrência de metadado que a limpeza de fato removeu."""
    if not candidatos:
        return
    restantes = " ".join(str(v) for v in (doc.metadata or {}).values() if v)
    try:
        restantes += " " + (doc.get_xml_metadata() or "")
    except Exception:  # pragma: no cover
        pass
    for candidato in candidatos:
        alvo = candidato.valor.strip()
        if alvo and alvo in restantes:
            candidato.status = Status.FALHA_CRITICA
            candidato.falha = "Dado pessoal permanece nos metadados do documento."
            resultado.falhas.append(
                Risco(
                    "METADADO_NAO_REMOVIDO",
                    "Ocorrência confirmada permanece nos metadados do documento.",
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                    detalhe=f"categoria {candidato.categoria.value}, id {candidato.id}",
                )
            )
        else:
            candidato.status = Status.REDIGIDO
            resultado.redacoes_aplicadas += 1


def _conferir_areas(
    saida: Path, candidatos: list[Candidato], resultado: ResultadoRedacao
) -> None:
    """Reabre o documento gravado e confere visualmente as áreas redigidas."""
    try:
        doc = fitz.open(saida)
    except Exception as exc:  # pragma: no cover
        resultado.falhas.append(
            Risco(
                "CONFERENCIA_IMPOSSIVEL",
                "O documento de saída não pôde ser reaberto para conferência.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
                detalhe=str(exc)[:200],
            )
        )
        return
    with doc:
        for candidato in candidatos:
            if candidato.status != Status.REDIGIDO or not candidato.bboxes:
                continue
            if candidato.pagina >= doc.page_count:
                continue
            page = doc[candidato.pagina]
            for bbox in candidato.bboxes:
                texto_restante = page.get_textbox(fitz.Rect(bbox)).strip()
                alvo = candidato.valor.strip()
                if alvo and alvo in texto_restante:
                    candidato.status = Status.FALHA_CRITICA
                    candidato.falha = "Texto original ainda presente na área redigida."
                    resultado.falhas.append(
                        Risco(
                            "TEXTO_RESIDUAL_AREA",
                            "Conteúdo original permanece legível na área redigida.",
                            Severidade.CRITICO,
                            pagina=candidato.pagina,
                            bloqueia_aprovacao=True,
                        )
                    )
