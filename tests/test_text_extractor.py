"""Testes da extração de texto e do mapeamento de posições."""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.text_extractor import (
    bboxes_para_intervalo,
    extrair_pagina,
    linearizar_palavras,
    textos_de_formulario,
    textos_de_links,
)


def test_linearizacao_mantem_offsets():
    palavras = [
        (10.0, 10.0, 30.0, 20.0, "Pessoa", 0, 0, 0),
        (32.0, 10.0, 52.0, 20.0, "Teste", 0, 0, 1),
        (10.0, 22.0, 40.0, 32.0, "Alfa", 0, 1, 0),
    ]
    texto, posicoes = linearizar_palavras(palavras)
    assert texto == "Pessoa Teste\nAlfa"
    for posicao in posicoes:
        assert texto[posicao.inicio : posicao.fim] == posicao.texto


def test_bboxes_unem_palavras_contiguas_da_mesma_linha():
    palavras = [
        (10.0, 10.0, 30.0, 20.0, "Pessoa", 0, 0, 0),
        (32.0, 10.0, 52.0, 20.0, "Teste", 0, 0, 1),
    ]
    texto, posicoes = linearizar_palavras(palavras)
    caixas = bboxes_para_intervalo(posicoes, 0, len(texto))
    assert len(caixas) == 1
    assert caixas[0] == (10.0, 10.0, 52.0, 20.0)


def test_bboxes_separam_linhas_distintas():
    palavras = [
        (10.0, 10.0, 30.0, 20.0, "Pessoa", 0, 0, 0),
        (10.0, 40.0, 30.0, 50.0, "Alfa", 0, 1, 0),
    ]
    texto, posicoes = linearizar_palavras(palavras)
    caixas = bboxes_para_intervalo(posicoes, 0, len(texto))
    assert len(caixas) == 2


def test_extracao_de_pagina_real(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "01_texto_cpf.pdf")
    with doc:
        pagina = extrair_pagina(doc[0])
    assert pagina.examinada
    assert "529.982.247-25" in pagina.texto_pdf
    # Cada palavra deve apontar para o próprio trecho do texto linearizado.
    for posicao in pagina.palavras_pdf[:20]:
        assert pagina.texto_pdf[posicao.inicio : posicao.fim] == posicao.texto


def test_pagina_digitalizada_tem_texto_vazio(pasta_fixtures):
    doc = fitz.open(pasta_fixtures / "02_digitalizado.pdf")
    with doc:
        pagina = extrair_pagina(doc[0])
    assert pagina.texto_pdf.strip() == ""
    assert not pagina.examinada


def test_links_e_formularios_sao_lidos(tmp_path):
    doc = fitz.open()
    page = doc.new_page()
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(10, 10, 100, 30),
            "uri": "https://exemplo.invalido/?token=abc",
        }
    )
    widget = fitz.Widget()
    widget.field_name = "cpf_titular"
    widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    widget.field_value = "529.982.247-25"
    widget.rect = fitz.Rect(10, 50, 200, 70)
    page.add_widget(widget)
    destino = tmp_path / "formulario.pdf"
    doc.save(destino)
    doc.close()

    doc = fitz.open(destino)
    with doc:
        links = textos_de_links(doc[0])
        campos = textos_de_formulario(doc[0])
    assert any("token" in t for t, _ in links)
    assert any("529.982.247-25" in t for t, _ in campos)
