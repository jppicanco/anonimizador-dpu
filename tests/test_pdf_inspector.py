"""Testes da inspeção estrutural (itens 16 e 17 dos testes obrigatórios)."""

from __future__ import annotations

from anonimizador_dpu.core.models import Severidade, TipoPagina
from anonimizador_dpu.core.pdf_inspector import inspecionar


def test_pdf_de_texto_classificado_corretamente(pasta_fixtures, cfg):
    insp = inspecionar(pasta_fixtures / "01_texto_cpf.pdf", cfg)
    assert insp.erro_fatal is None
    assert insp.total_paginas == 1
    assert insp.paginas_texto == 1
    assert insp.sha256_entrada


def test_pdf_digitalizado_identificado(pasta_fixtures, cfg):
    insp = inspecionar(pasta_fixtures / "02_digitalizado.pdf", cfg)
    assert insp.paginas_digitalizadas == 1
    assert any(r.codigo == "PAGINAS_DIGITALIZADAS" for r in insp.riscos)


def test_pdf_hibrido_identificado(pasta_fixtures, cfg):
    insp = inspecionar(pasta_fixtures / "03_hibrido.pdf", cfg)
    assert insp.paginas_hibridas == 1
    assert insp.paginas[0].tipo == TipoPagina.HIBRIDA


def test_anotacoes_sao_sinalizadas(pasta_fixtures, cfg):
    insp = inspecionar(pasta_fixtures / "12_anotacao.pdf", cfg)
    assert insp.qtd_anotacoes >= 1
    assert any(r.codigo == "ANOTACOES" for r in insp.riscos)


def test_metadados_sao_listados_sem_expor_valores(pasta_fixtures, cfg):
    insp = inspecionar(pasta_fixtures / "13_metadados.pdf", cfg)
    assert "author" in insp.metadados
    exportado = insp.to_dict()
    assert "chaves_metadados" in exportado
    assert "author" in exportado["chaves_metadados"]
    # O relatório lista apenas as chaves, nunca os valores dos metadados.
    assert "Pessoa Teste Alfa" not in str(exportado)


def test_anexo_bloqueia_aprovacao(pasta_fixtures, cfg):
    """Item 14 — arquivo incorporado não suportado nunca é ignorado em silêncio."""
    insp = inspecionar(pasta_fixtures / "14_anexo.pdf", cfg)
    assert insp.arquivos_incorporados
    riscos = [r for r in insp.riscos if r.codigo == "ARQUIVOS_INCORPORADOS"]
    assert riscos and riscos[0].bloqueia_aprovacao


def test_pdf_malformado_nao_derruba_a_aplicacao(pasta_fixtures, cfg):
    """Item 16 — PDF malformado produz erro controlado e bloqueio."""
    insp = inspecionar(pasta_fixtures / "16_malformado.pdf", cfg)
    assert insp.riscos_bloqueantes(), "PDF malformado deve bloquear a aprovação"
    assert insp.erro_fatal is not None or any(
        r.codigo == "PDF_REPARADO" for r in insp.riscos
    )


def test_assinatura_digital_e_detectada(pasta_fixtures, cfg):
    """Item 17 — assinatura digital é detectada e informada como risco crítico."""
    insp = inspecionar(pasta_fixtures / "17_assinatura.pdf", cfg)
    assert insp.assinaturas
    risco = next(r for r in insp.riscos if r.codigo == "ASSINATURA_DIGITAL")
    assert risco.bloqueia_aprovacao
    assert risco.severidade == Severidade.CRITICO


def test_arquivo_inexistente_gera_risco(tmp_path, cfg):
    insp = inspecionar(tmp_path / "nao_existe.pdf", cfg)
    assert insp.erro_fatal
    assert any(r.codigo == "ENTRADA_INVALIDA" for r in insp.riscos)


def test_arquivo_nao_pdf_recusado(tmp_path, cfg):
    falso = tmp_path / "documento.txt"
    falso.write_text("não é um PDF", encoding="utf-8")
    insp = inspecionar(falso, cfg)
    assert insp.erro_fatal
