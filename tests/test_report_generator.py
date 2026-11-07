"""Testes dos relatórios: conteúdo obrigatório e ausência de dados pessoais."""

from __future__ import annotations

import json

from anonimizador_dpu.core.pipeline import Sessao
from anonimizador_dpu.core.report_generator import (
    montar_html,
    montar_json,
    resumo_lote,
    salvar_html,
    salvar_json,
)
from tests.conftest import confirmar_tudo
from tests.fixtures.gerador import CEP_TESTE, CPF_ALFA, NOME_ALFA, PROCESSO_TESTE


def _relatorio(pasta_fixtures, pasta_saida, cfg):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    return sessao.processar(entrada, pasta_saida), sessao


def test_relatorio_json_tem_campos_obrigatorios(pasta_fixtures, pasta_saida, cfg):
    relatorio, _ = _relatorio(pasta_fixtures, pasta_saida, cfg)
    dados = montar_json(relatorio, cfg)

    assert dados["documento"]["arquivo_saida"]
    assert dados["documento"]["processado_em"]
    assert dados["aplicativo"]["versao"]
    assert dados["estrutura"]["total_paginas"] == 1
    assert dados["cobertura"]["paginas_processadas_por_texto"] == 1
    assert dados["ocorrencias"]["por_categoria"]
    assert dados["redacao"]["areas_aplicadas"] > 0
    assert dados["validacao"]["veredito"]
    assert len(dados["documento"]["sha256_saida"]) == 64
    assert dados["aviso"]


def test_relatorio_nao_contem_dados_pessoais(pasta_fixtures, pasta_saida, cfg):
    relatorio, _ = _relatorio(pasta_fixtures, pasta_saida, cfg)
    texto_json = json.dumps(montar_json(relatorio, cfg), ensure_ascii=False)
    html = montar_html(relatorio, cfg)

    for proibido in (CPF_ALFA, NOME_ALFA, PROCESSO_TESTE, CEP_TESTE):
        assert proibido not in texto_json, f"{proibido} vazou para o relatório JSON"
        assert proibido not in html, f"{proibido} vazou para o relatório HTML"

    # Também não pode vazar a forma sem pontuação dos números.
    assert CPF_ALFA.replace(".", "").replace("-", "") not in texto_json


def test_relatorios_sao_gravados(pasta_fixtures, pasta_saida, cfg, tmp_path):
    relatorio, _ = _relatorio(pasta_fixtures, pasta_saida, cfg)
    destino_json = salvar_json(relatorio, cfg, tmp_path / "rel.json")
    destino_html = salvar_html(relatorio, cfg, tmp_path / "rel.html")
    assert destino_json.exists() and destino_json.stat().st_size > 100
    assert destino_html.exists()
    assert "<html" in destino_html.read_text(encoding="utf-8").lower()


def test_html_exibe_o_veredito_e_os_limites(pasta_fixtures, pasta_saida, cfg):
    relatorio, _ = _relatorio(pasta_fixtures, pasta_saida, cfg)
    html = montar_html(relatorio, cfg)
    assert "APROVADO NOS TESTES AUTOMATIZADOS" in html
    assert "não prova anonimização integral" in html
    assert "Limites desta verificação" in html


def test_resumo_de_lote(pasta_fixtures, pasta_saida, cfg):
    relatorio, sessao = _relatorio(pasta_fixtures, pasta_saida, cfg)
    resumo = resumo_lote([relatorio])
    assert resumo["documentos"] == 1
    assert resumo["aprovados_nos_testes"] + resumo["com_pendencias"] == 1
    assert resumo["aviso"]
