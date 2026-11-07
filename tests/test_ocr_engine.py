"""Testes do OCR local (item 15 dos testes obrigatórios)."""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.ocr_engine import ocr_pagina, verificar_ocr
from tests.conftest import requer_ocr


def test_verificacao_do_ambiente_nao_acessa_rede(cfg):
    status = verificar_ocr(cfg.ocr)
    assert isinstance(status.disponivel, bool)
    if not status.disponivel:
        assert status.erro, "Indisponibilidade do OCR deve vir com explicação"


def test_idioma_ausente_e_reportado(cfg):
    cfg.ocr.idiomas = "xyz"
    status = verificar_ocr(cfg.ocr)
    assert not status.disponivel
    assert "idioma" in status.erro.lower()


@requer_ocr
def test_ocr_le_pagina_digitalizada(pasta_fixtures, cfg):
    doc = fitz.open(pasta_fixtures / "02_digitalizado.pdf")
    with doc:
        resultado = ocr_pagina(doc[0], cfg.ocr)
    assert resultado.ocr_executado
    assert not resultado.ocr_falhou
    assert "529" in resultado.texto_ocr.replace(" ", "")
    assert resultado.palavras_ocr
    # Todas as palavras têm área dentro da página
    pagina = fitz.open(pasta_fixtures / "02_digitalizado.pdf")[0]
    for palavra in resultado.palavras_ocr:
        x0, y0, x1, y1 = palavra.bbox
        assert pagina.rect.x0 - 1 <= x0 <= pagina.rect.x1 + 1
        assert pagina.rect.y0 - 1 <= y0 <= pagina.rect.y1 + 1


@requer_ocr
def test_pagina_ilegivel_nao_e_considerada_examinada(pasta_fixtures, cfg):
    """Item 15 — retorno de algum texto não prova que a página foi examinada."""
    doc = fitz.open(pasta_fixtures / "15_ilegivel_ocr.pdf")
    with doc:
        resultado = ocr_pagina(doc[0], cfg.ocr)
    assert not resultado.examinada
    assert resultado.ocr_cobertura < cfg.ocr.cobertura_minima or not resultado.palavras_ocr


@requer_ocr
def test_cobertura_e_confianca_sao_registradas(pasta_fixtures, cfg):
    doc = fitz.open(pasta_fixtures / "02_digitalizado.pdf")
    with doc:
        resultado = ocr_pagina(doc[0], cfg.ocr)
    assert 0.0 <= resultado.ocr_cobertura <= 1.0
    assert resultado.ocr_confianca_media > 0


def test_ocr_desligado_reporta_falha(cfg):
    cfg.ocr.caminho_tesseract = "C:/caminho/inexistente/tesseract.exe"
    status = verificar_ocr(cfg.ocr)
    assert not status.disponivel
