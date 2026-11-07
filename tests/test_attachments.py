"""Testes dos arquivos incorporados (item 14 dos testes obrigatórios)."""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.attachment_inspector import (
    anexos_residuais,
    listar_anexos,
    riscos_de_anexos,
)


def test_anexo_e_listado_sem_ser_executado(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "14_anexo.pdf")
    with doc:
        anexos = listar_anexos(doc)
    assert len(anexos) == 1
    assert anexos[0].nome == "planilha_teste.xlsx"
    assert not anexos[0].suportado, "Formato não suportado deve ser sinalizado"


def test_anexo_mantido_bloqueia_aprovacao(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "14_anexo.pdf")
    with doc:
        anexos = listar_anexos(doc)
    riscos = riscos_de_anexos(anexos, serao_removidos=False)
    assert riscos and riscos[0].bloqueia_aprovacao


def test_anexo_removido_gera_aviso(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "14_anexo.pdf")
    with doc:
        anexos = listar_anexos(doc)
    riscos = riscos_de_anexos(anexos, serao_removidos=True)
    assert riscos
    assert not riscos[0].bloqueia_aprovacao
    assert "NÃO foi analisado" in riscos[0].descricao


def test_documento_sem_anexos(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "01_texto_cpf.pdf")
    with doc:
        assert listar_anexos(doc) == []
        assert anexos_residuais(doc) == []
