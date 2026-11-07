"""Regressões achadas no ensaio da aula 5 do curso (29/10/2026).

1. A localidade "PARÁ", comparada sem acento, casava com a preposição "para"
   e reprovava todo documento do Pará.
2. O número de processo no título do PDF virava candidato de metadado sem área
   na página e reprovava o documento por AREA_INDETERMINADA, embora a limpeza
   de metadados o removesse.
"""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.models import Origem, Status, Veredito
from anonimizador_dpu.core.output_validator import _minusculo, _normalizar, _valor_presente
from anonimizador_dpu.core.pipeline import Sessao
from tests.conftest import confirmar_tudo

PROCESSO = "1009876-12.2026.4.01.3900"


def _pdf(caminho, texto: str, titulo: str | None = None):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_textbox(fitz.Rect(60, 60, 535, 790), texto, fontsize=11, fontname="helv")
    if titulo:
        doc.set_metadata({"title": titulo})
    doc.save(caminho)
    doc.close()
    return caminho


def _presente(valor: str, texto: str) -> bool:
    return _valor_presente(valor, _normalizar(texto), "", _minusculo(texto))


class TestComparacao:
    def test_localidade_nao_casa_com_a_preposicao(self):
        assert not _presente("PARÁ", "Requer prazo para manifestação, separado do pedido.")

    def test_localidade_continua_sendo_achada(self):
        assert _presente("PARÁ", "Estado do Pará, capital Belém")
        assert _presente("PARÁ", "SEÇÃO JUDICIÁRIA DO PARÁ")

    def test_nome_nao_casa_dentro_de_outra_palavra(self):
        assert not _presente("Lima", "a liminar foi deferida")

    def test_nome_sem_acento_no_ocr_continua_sendo_achado(self):
        assert _presente("Josué Ribamar Cavalcante", "Eu, JOSUE RIBAMAR\nCAVALCANTE, declaro")


def test_documento_do_para_nao_e_reprovado_pela_preposicao(tmp_path, pasta_saida, cfg):
    entrada = _pdf(
        tmp_path / "para.pdf",
        "Requerente: JOSUÉ RIBAMAR CAVALCANTE, residente no ESTADO DO PARÁ, "
        "vem requerer prazo para manifestação e para juntada de documentos.",
    )
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)

    codigos = [r.codigo for r in relatorio.validacao.riscos]
    assert "IDENTIFICADOR_RESIDUAL" not in codigos
    assert relatorio.veredito == Veredito.APROVADO_TESTES


def test_processo_no_titulo_sai_pela_limpeza_de_metadados(tmp_path, pasta_saida, cfg):
    entrada = _pdf(
        tmp_path / "titulo.pdf",
        f"Processo nº {PROCESSO}\nRequerente: JOSUÉ RIBAMAR CAVALCANTE, brasileiro.",
        titulo=f"Processo {PROCESSO}",
    )
    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    de_metadado = [c for c in sessao.gerenciador.candidatos if c.origem == Origem.METADADO]
    assert de_metadado, "o título deveria gerar candidato de metadado"

    relatorio = sessao.processar(entrada, pasta_saida)

    assert all(c.status != Status.FALHA_CRITICA for c in de_metadado)
    assert "AREA_INDETERMINADA" not in [r.codigo for r in relatorio.redacao.falhas]
    assert relatorio.veredito == Veredito.APROVADO_TESTES
    with fitz.open(pasta_saida / "titulo_ANONIMIZADO.pdf") as saida:
        assert PROCESSO not in " ".join(str(v) for v in saida.metadata.values() if v)
