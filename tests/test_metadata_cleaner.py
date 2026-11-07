"""Testes da limpeza de metadados e estruturas (itens 12 e 13 dos testes obrigatórios)."""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.config import Config
from anonimizador_dpu.core.metadata_cleaner import (
    higienizar,
    limpar_documento,
    metadados_residuais,
)
from anonimizador_dpu.core.text_extractor import (
    metadados_textuais,
    textos_de_anotacoes,
)
from tests.fixtures.gerador import CPF_ALFA, NOME_ALFA


def test_metadados_com_nome_sao_removidos(pasta_fixtures, pasta_saida, cfg):
    """Item 13 — metadados contendo nome fictício."""
    doc = fitz.open(pasta_fixtures / "13_metadados.pdf")
    with doc:
        antes = metadados_textuais(doc)
        assert NOME_ALFA in str(antes)
        removidos, _, nao_tratadas = limpar_documento(doc, cfg.redacao)
        assert "author" in removidos
        destino = pasta_saida / "sem_metadados.pdf"
        # garbage=4 é o modo usado pelo aplicativo: elimina os objetos antigos,
        # sem o que o dicionário de metadados permaneceria no arquivo.
        doc.save(destino, garbage=4, deflate=True, clean=True)

    conferencia = fitz.open(destino)
    with conferencia:
        assert not metadados_residuais(conferencia)
    conteudo = destino.read_bytes().decode("latin-1", errors="ignore")
    assert NOME_ALFA not in conteudo
    assert CPF_ALFA not in conteudo


def test_anotacoes_sao_lidas_e_removidas(pasta_fixtures, pasta_saida, cfg):
    """Item 12 — dados pessoais dentro de anotação."""
    doc = fitz.open(pasta_fixtures / "12_anotacao.pdf")
    with doc:
        textos = textos_de_anotacoes(doc[0])
        assert textos, "A anotação deve ser lida pela extração"
        assert any(CPF_ALFA in t for t, _ in textos)
        _, estruturas, _ = limpar_documento(doc, cfg.redacao)
        assert any("anota" in e for e in estruturas)
        destino = pasta_saida / "sem_anotacao.pdf"
        doc.save(destino, garbage=4, clean=True)

    conferencia = fitz.open(destino)
    with conferencia:
        assert len(list(conferencia[0].annots() or [])) == 0
    conteudo = destino.read_bytes().decode("latin-1", errors="ignore")
    assert CPF_ALFA not in conteudo


def test_marcadores_e_links_removidos(pasta_fixtures, pasta_saida, cfg):
    origem = pasta_saida / "com_links.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "documento de teste")
    page.insert_link(
        {
            "kind": fitz.LINK_URI,
            "from": fitz.Rect(40, 40, 200, 60),
            "uri": "https://exemplo.invalido/?token=segredo",
        }
    )
    doc.set_toc([[1, "Capítulo de Pessoa Teste Alfa", 1]])
    doc.save(origem)
    doc.close()

    # O PyMuPDF só materializa os links depois de gravar: o documento é reaberto.
    doc = fitz.open(origem)
    with doc:
        assert doc[0].get_links()
        _, estruturas, _ = limpar_documento(doc, cfg.redacao)
        destino = pasta_saida / "sem_links.pdf"
        doc.save(destino, garbage=4, clean=True)
    assert any("link" in e for e in estruturas)
    assert any("marcador" in e for e in estruturas)

    conferencia = fitz.open(destino)
    with conferencia:
        assert conferencia[0].get_links() == []
        assert conferencia.get_toc() == []


def test_higienizacao_estrutural_nao_falha(pasta_fixtures, pasta_saida):
    doc = fitz.open(pasta_fixtures / "01_texto_cpf.pdf")
    with doc:
        aplicadas = higienizar(doc)
        assert aplicadas
        assert not any("falhou" in a for a in aplicadas)


def test_configuracao_preserva_estruturas_quando_solicitado(pasta_fixtures):
    cfg = Config()
    cfg.redacao.remover_anexos = False
    doc = fitz.open(pasta_fixtures / "14_anexo.pdf")
    with doc:
        _, _, nao_tratadas = limpar_documento(doc, cfg.redacao)
    assert any("anexo" in n or "incorporado" in n for n in nao_tratadas)
