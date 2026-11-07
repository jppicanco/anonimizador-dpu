"""Testes da redação efetiva (itens 1, 11 e 21 dos testes obrigatórios)."""

from __future__ import annotations

import fitz
import pytest

from anonimizador_dpu.core.config import Config
from anonimizador_dpu.core.entity_detector import detectar_na_pagina
from anonimizador_dpu.core.models import Candidato, Categoria, Status
from anonimizador_dpu.core.redaction_engine import aplicar_redacoes
from anonimizador_dpu.core.security import sha256_arquivo
from anonimizador_dpu.core.text_extractor import extrair_pagina
from tests.fixtures.gerador import CPF_ALFA, NOME_ALFA


def _candidatos_do_pdf(caminho, cfg: Config) -> list[Candidato]:
    doc = fitz.open(caminho)
    encontrados: list[Candidato] = []
    with doc:
        for page in doc:
            pagina = extrair_pagina(page)
            encontrados.extend(detectar_na_pagina(caminho.name, pagina, cfg))
    for c in encontrados:
        c.status = Status.CONFIRMADO
        c.pseudonimo = c.pseudonimo or f"[{c.categoria.value}_1]"
    return encontrados


def test_texto_original_e_removido_do_pdf(pasta_fixtures, pasta_saida, cfg):
    """Item 1 — PDF com texto selecionável: o conteúdo é removido, não coberto."""
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida.pdf"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    resultado = aplicar_redacoes(entrada, saida, candidatos, cfg)

    assert resultado.redacoes_aplicadas > 0
    assert saida.exists()

    doc = fitz.open(saida)
    with doc:
        texto = "".join(p.get_text() for p in doc)
    assert CPF_ALFA not in texto
    assert CPF_ALFA.replace(".", "").replace("-", "") not in texto.replace(
        ".", ""
    ).replace("-", "")
    assert NOME_ALFA not in texto


def test_conteudo_removido_tambem_do_fluxo_interno(pasta_fixtures, pasta_saida, cfg):
    """A verificação vai além da extração de texto: inspeciona os bytes do PDF."""
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida_interna.pdf"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    aplicar_redacoes(entrada, saida, candidatos, cfg)

    doc = fitz.open(saida)
    with doc:
        fluxos = []
        for page in doc:
            for xref in page.get_contents():
                fluxos.append(doc.xref_stream(xref) or b"")
    conteudo = b"".join(fluxos).decode("latin-1", errors="ignore")
    assert "529.982.247-25" not in conteudo
    assert "Pessoa Teste Alfa" not in conteudo


def test_pseudonimo_substitui_o_conteudo(pasta_fixtures, pasta_saida, cfg):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida_pseudonimo.pdf"
    cfg.redacao.modo = "pseudonimo"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    aplicar_redacoes(entrada, saida, candidatos, cfg)
    doc = fitz.open(saida)
    with doc:
        texto = "".join(p.get_text() for p in doc)
    assert "[" in texto and "]" in texto


def test_modo_tarja_nao_escreve_rotulo(pasta_fixtures, pasta_saida, cfg):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida_tarja.pdf"
    cfg.redacao.modo = "tarja"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    aplicar_redacoes(entrada, saida, candidatos, cfg)
    doc = fitz.open(saida)
    with doc:
        texto = "".join(p.get_text() for p in doc)
    assert CPF_ALFA not in texto
    assert "[CPF" not in texto


def test_original_permanece_intacto(pasta_fixtures, pasta_saida, cfg):
    """Item 9 dos critérios de aceitação — o original nunca é alterado."""
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    antes = sha256_arquivo(entrada)
    candidatos = _candidatos_do_pdf(entrada, cfg)
    aplicar_redacoes(entrada, pasta_saida / "saida2.pdf", candidatos, cfg)
    assert sha256_arquivo(entrada) == antes


def test_ocorrencia_sem_area_vira_falha_critica(pasta_fixtures, pasta_saida, cfg):
    """Item 21 — falha no mecanismo de redação não passa despercebida.

    Uma ocorrência confirmada sem coordenadas seguras não é redigida "no
    palpite": ela é marcada como falha crítica e bloqueia a aprovação.
    """
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida_falha.pdf"
    candidato = Candidato(
        documento=entrada.name,
        pagina=0,
        categoria=Categoria.CPF,
        valor="529.982.247-25",
        bboxes=[],
        status=Status.CONFIRMADO,
        bbox_incerta=True,
    )
    resultado = aplicar_redacoes(entrada, saida, [candidato], cfg)
    assert candidato.status == Status.FALHA_CRITICA
    assert any(r.codigo == "AREA_INDETERMINADA" for r in resultado.falhas)
    assert any(r.bloqueia_aprovacao for r in resultado.falhas)


def test_cabecalho_e_rodape_sao_redigidos(pasta_fixtures, pasta_saida, cfg):
    """Item 11 — dados pessoais em cabeçalho e rodapé de todas as páginas."""
    entrada = pasta_fixtures / "11_cabecalho_rodape.pdf"
    saida = pasta_saida / "saida_cabecalho.pdf"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    assert len({c.pagina for c in candidatos}) >= 3
    aplicar_redacoes(entrada, saida, candidatos, cfg)
    doc = fitz.open(saida)
    with doc:
        texto = "".join(p.get_text() for p in doc)
    assert CPF_ALFA not in texto
    assert NOME_ALFA not in texto


def test_nome_repetido_em_varias_paginas(pasta_fixtures, pasta_saida, cfg):
    """Item 4 — nome repetido em dezenas de ocorrências."""
    entrada = pasta_fixtures / "04_nome_repetido.pdf"
    saida = pasta_saida / "saida_repetido.pdf"
    candidatos = _candidatos_do_pdf(entrada, cfg)
    nomes = [c for c in candidatos if c.categoria == Categoria.NOME_PESSOA]
    assert len(nomes) >= 12
    aplicar_redacoes(entrada, saida, candidatos, cfg)
    doc = fitz.open(saida)
    with doc:
        texto = "".join(p.get_text() for p in doc)
    assert NOME_ALFA not in texto


def test_hash_da_saida_e_calculado(pasta_fixtures, pasta_saida, cfg):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "saida_hash.pdf"
    resultado = aplicar_redacoes(entrada, saida, _candidatos_do_pdf(entrada, cfg), cfg)
    assert len(resultado.sha256_saida) == 64
    assert resultado.sha256_saida == sha256_arquivo(saida)
