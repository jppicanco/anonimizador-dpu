"""Testes de ponta a ponta (itens 2, 3, 10, 22, 23 e 24 dos testes obrigatórios)."""

from __future__ import annotations

import socket
import threading

import fitz
import pytest

from anonimizador_dpu.core.models import Categoria, Status, Veredito
from anonimizador_dpu.core.pipeline import Sessao
from anonimizador_dpu.core.security import sha256_arquivo
from tests.conftest import confirmar_tudo, requer_ocr
from tests.fixtures.gerador import (
    CPF_ALFA,
    CPF_BETA,
    NOME_ALFA,
    NOME_GAMA,
    PROCESSO_TESTE,
    pdf_multiplas_paginas_lote,
)


def _texto_de(caminho) -> str:
    doc = fitz.open(caminho)
    with doc:
        return "".join(p.get_text() for p in doc)


def test_fluxo_completo_documento_de_texto(pasta_fixtures, pasta_saida, cfg):
    """Item 1 e critérios de aceitação 2, 5, 6, 8 e 9."""
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    hash_antes = sha256_arquivo(entrada)

    sessao = Sessao(cfg)
    inspecoes = sessao.inspecionar([entrada])
    assert inspecoes[0].total_paginas == 1

    candidatos = sessao.analisar(entrada)
    assert any(c.categoria == Categoria.CPF for c in candidatos)
    confirmar_tudo(sessao)

    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito == Veredito.APROVADO_TESTES
    assert sha256_arquivo(entrada) == hash_antes  # original intacto

    saida = pasta_saida / "01_texto_cpf_ANONIMIZADO.pdf"
    assert saida.exists()
    texto = _texto_de(saida)
    assert CPF_ALFA not in texto
    assert NOME_ALFA not in texto
    assert PROCESSO_TESTE not in texto

    # Relatórios gerados ao lado da saída
    assert (pasta_saida / "01_texto_cpf_ANONIMIZADO_relatorio.json").exists()
    assert (pasta_saida / "01_texto_cpf_ANONIMIZADO_relatorio.html").exists()


@requer_ocr
def test_fluxo_completo_documento_digitalizado(pasta_fixtures, pasta_saida, cfg):
    """Item 2 — PDF digitalizado com CPF e endereço, processado por OCR local."""
    entrada = pasta_fixtures / "02_digitalizado.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)

    assert any(c.categoria == Categoria.CPF for c in candidatos)
    assert all(c.bboxes for c in candidatos if c.status != Status.REJEITADO)
    confirmar_tudo(sessao)

    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.paginas_por_ocr == 1
    assert relatorio.veredito == Veredito.APROVADO_TESTES
    assert relatorio.validacao.paginas_verificadas_ocr == 1
    assert relatorio.validacao.residuais_conhecidos == 0


@requer_ocr
def test_pagina_hibrida_trata_texto_e_imagem(pasta_fixtures, pasta_saida, cfg):
    """Item 3 — camada textual e camada visual tratadas separadamente."""
    entrada = pasta_fixtures / "03_hibrido.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)

    origens = {c.origem.value for c in candidatos}
    # Em uma página híbrida o OCR cobre a página inteira, inclusive o texto
    # nativo: as ocorrências vistas pelas duas fontes aparecem como TEXTO_E_OCR,
    # e as que só existem na imagem aparecem como OCR.
    assert origens & {"TEXTO", "TEXTO_E_OCR"}
    assert origens & {"OCR", "TEXTO_E_OCR"}
    assert "OCR" in origens, "Dados presentes apenas na imagem devem ser localizados"

    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    saida = pasta_saida / "03_hibrido_ANONIMIZADO.pdf"
    texto = _texto_de(saida)
    assert NOME_ALFA not in texto
    assert relatorio.validacao.residuais_conhecidos == 0


@requer_ocr
def test_nome_apenas_em_imagem_e_encontrado(pasta_fixtures, pasta_saida, cfg):
    """Item 10 — nome presente apenas dentro de imagem incorporada."""
    entrada = pasta_fixtures / "10_nome_em_imagem.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)
    nomes = [c for c in candidatos if c.categoria == Categoria.NOME_PESSOA]
    assert nomes, "O nome na imagem deve ser localizado por OCR"
    assert all(c.bboxes for c in nomes)

    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.validacao.residuais_conhecidos == 0


def test_cancelamento_encerra_de_forma_controlada(pasta_fixtures, pasta_saida, cfg):
    """Item 22 — cancelamento durante o processamento."""
    entrada = pasta_fixtures / "04_nome_repetido.pdf"
    hash_antes = sha256_arquivo(entrada)
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)

    sessao.cancelar.set()
    relatorio = sessao.processar(entrada, pasta_saida)

    assert relatorio.cancelado
    assert relatorio.veredito == Veredito.REPROVADO
    assert "cancelado" in (relatorio.erro or "").lower()
    assert sha256_arquivo(entrada) == hash_antes


def test_cancelamento_durante_a_analise(pasta_fixtures, cfg):
    entrada = pasta_fixtures / "04_nome_repetido.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.cancelar.set()
    sessao.analisar(entrada)
    paginas = sessao.paginas.get(entrada.name, [])
    assert len(paginas) < 12


def test_processamento_em_lote_preserva_ordem(pasta_fixtures, pasta_saida, cfg):
    """Item 23 — processamento em lote."""
    arquivos = [
        pasta_fixtures / "01_texto_cpf.pdf",
        pasta_fixtures / "06_cpf_formatos.pdf",
        pasta_fixtures / "08_processo_cnj.pdf",
    ]
    sessao = Sessao(cfg)
    sessao.inspecionar(arquivos)
    for arquivo in arquivos:
        sessao.analisar(arquivo)
    confirmar_tudo(sessao)

    relatorios = sessao.processar_lote(pasta_saida)
    assert [r.arquivo_entrada for r in relatorios] == [a.name for a in arquivos]
    assert all(r.arquivo_saida for r in relatorios)
    for arquivo in arquivos:
        assert (pasta_saida / f"{arquivo.stem}_ANONIMIZADO.pdf").exists()


def test_consistencia_de_pseudonimos_entre_documentos(tmp_path, pasta_saida, cfg):
    """Item 24 — a mesma pessoa recebe o mesmo pseudônimo em todos os documentos."""
    doc1 = pdf_multiplas_paginas_lote(tmp_path / "peca1.pdf", NOME_ALFA, CPF_ALFA)
    doc2 = pdf_multiplas_paginas_lote(tmp_path / "peca2.pdf", NOME_ALFA, CPF_ALFA)
    doc3 = pdf_multiplas_paginas_lote(tmp_path / "peca3.pdf", "Pessoa Teste Beta", CPF_BETA)

    sessao = Sessao(cfg)
    sessao.inspecionar([doc1, doc2, doc3])
    for documento in (doc1, doc2, doc3):
        sessao.analisar(documento)

    cpfs = {
        c.documento: c.pseudonimo
        for c in sessao.gerenciador.candidatos
        if c.categoria == Categoria.CPF
    }
    assert cpfs["peca1.pdf"] == cpfs["peca2.pdf"]
    assert cpfs["peca3.pdf"] != cpfs["peca1.pdf"]

    nomes = {
        c.documento: c.pseudonimo
        for c in sessao.gerenciador.candidatos
        if c.categoria == Categoria.NOME_PESSOA
    }
    assert nomes["peca1.pdf"] == nomes["peca2.pdf"]


def test_processamento_nao_usa_rede(pasta_fixtures, pasta_saida, cfg, monkeypatch):
    """Item 26 — verificação de que o processamento não depende de conexão externa.

    Qualquer tentativa de abrir socket durante o processamento é registrada.
    """
    tentativas: list[str] = []
    original = socket.socket

    class SocketVigiado(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            tentativas.append("socket")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(socket, "socket", SocketVigiado)

    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)

    assert tentativas == [], "Nenhum socket deve ser aberto durante o processamento"
    assert relatorio.veredito == Veredito.APROVADO_TESTES


def test_falsos_positivos_em_texto_juridico(pasta_fixtures, pasta_saida, cfg):
    """Item 18 — texto jurídico sem dados pessoais não gera ocorrências."""
    entrada = pasta_fixtures / "18_falsos_positivos.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)
    assert candidatos == [], (
        "Falsos positivos: "
        + str([(c.categoria.value, c.valor) for c in candidatos])
    )


def test_nomes_iguais_pessoas_distintas(pasta_fixtures, pasta_saida, cfg):
    """Item 5 — duas pessoas com o mesmo nome podem ser separadas na revisão."""
    entrada = pasta_fixtures / "05_nomes_iguais.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)
    nomes = [c for c in candidatos if c.categoria == Categoria.NOME_PESSOA]
    assert nomes
    # As duas menções ao mesmo nome compartilham o pseudônimo por padrão…
    assert len({c.pseudonimo for c in nomes}) == 1
    # …e o usuário pode separá-las explicitamente.
    if len(nomes) > 1:
        sessao.gerenciador.separar_entidade(nomes[1].id, "testemunha")
        assert nomes[0].pseudonimo != nomes[1].pseudonimo


def test_pdf_malformado_nao_interrompe_o_lote(pasta_fixtures, pasta_saida, cfg):
    """Item 16 — PDF malformado é reportado, sem derrubar o processamento."""
    arquivos = [pasta_fixtures / "16_malformado.pdf", pasta_fixtures / "01_texto_cpf.pdf"]
    sessao = Sessao(cfg)
    sessao.inspecionar(arquivos)
    for arquivo in arquivos:
        sessao.analisar(arquivo)
    confirmar_tudo(sessao)
    relatorios = sessao.processar_lote(pasta_saida)
    assert len(relatorios) == 2
    assert relatorios[0].veredito != Veredito.APROVADO_TESTES
    assert relatorios[1].veredito == Veredito.APROVADO_TESTES


def test_dados_bancarios_em_tabela(pasta_fixtures, pasta_saida, cfg):
    """Item 9 — dados bancários em tabela."""
    entrada = pasta_fixtures / "09_dados_bancarios.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)
    categorias = {c.categoria for c in candidatos}
    assert Categoria.CONTA_BANCARIA in categorias
    assert Categoria.AGENCIA_BANCARIA in categorias
    assert Categoria.CHAVE_PIX in categorias
    confirmar_tudo(sessao)
    sessao.processar(entrada, pasta_saida)
    texto = _texto_de(pasta_saida / "09_dados_bancarios_ANONIMIZADO.pdf")
    assert "12345-6" not in texto
    assert "3f2504e0-4f89-11d3-9a0c-0305e82c3301" not in texto


def test_anotacao_com_dados_e_tratada(pasta_fixtures, pasta_saida, cfg):
    """Item 12 — dados pessoais em anotação."""
    entrada = pasta_fixtures / "12_anotacao.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    candidatos = sessao.analisar(entrada)
    assert any(c.origem.value == "ANOTACAO" for c in candidatos)
    confirmar_tudo(sessao)
    sessao.processar(entrada, pasta_saida)
    saida = pasta_saida / "12_anotacao_ANONIMIZADO.pdf"
    conteudo = saida.read_bytes().decode("latin-1", errors="ignore")
    assert CPF_ALFA not in conteudo


def test_metadados_sao_limpos_no_fluxo(pasta_fixtures, pasta_saida, cfg):
    """Item 13 — metadados contendo nome fictício."""
    entrada = pasta_fixtures / "13_metadados.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.redacao.metadados_removidos
    assert not relatorio.validacao.metadados_residuais
    saida = pasta_saida / "13_metadados_ANONIMIZADO.pdf"
    conteudo = saida.read_bytes().decode("latin-1", errors="ignore")
    assert NOME_ALFA not in conteudo


@requer_ocr
def test_pagina_ilegivel_impede_aprovacao(pasta_fixtures, pasta_saida, cfg):
    """Item 15 — página ilegível para OCR impede a aprovação automática."""
    entrada = pasta_fixtures / "15_ilegivel_ocr.pdf"
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.paginas_nao_examinadas, "Página sem cobertura deve ser registrada"
    assert relatorio.veredito != Veredito.APROVADO_TESTES


def test_sessao_em_thread_separada(pasta_fixtures, pasta_saida, cfg):
    """A sessão funciona fora da thread principal (como na interface gráfica)."""
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao = Sessao(cfg)
    resultado = {}

    def executar():
        sessao.inspecionar([entrada])
        sessao.analisar(entrada)
        confirmar_tudo(sessao)
        resultado["relatorio"] = sessao.processar(entrada, pasta_saida)

    t = threading.Thread(target=executar)
    t.start()
    t.join(timeout=120)
    assert not t.is_alive()
    assert resultado["relatorio"].veredito == Veredito.APROVADO_TESTES
