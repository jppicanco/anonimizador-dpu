"""Testes da validação independente (itens 19, 20 e 21 dos testes obrigatórios)."""

from __future__ import annotations

import fitz

from anonimizador_dpu.core.models import (
    Candidato,
    Categoria,
    Inspecao,
    ResultadoValidacao,
    Risco,
    Severidade,
    Status,
    Veredito,
)
from anonimizador_dpu.core.output_validator import decidir_veredito, validar_saida
from anonimizador_dpu.core.pipeline import Sessao
from tests.conftest import confirmar_tudo
from tests.fixtures.gerador import CPF_ALFA


def test_reabertura_e_reextracao(pasta_fixtures, pasta_saida, cfg):
    """Item 19 — o PDF de saída é fechado, reaberto e reextraído."""
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)

    validacao = relatorio.validacao
    assert validacao is not None
    assert validacao.abriu_corretamente
    assert validacao.paginas_verificadas_texto == 1
    assert validacao.areas_redacao_conferidas > 0


def test_identificador_residual_reprova_o_documento(pasta_fixtures, pasta_saida, cfg):
    """Item 20 — pesquisa por identificadores originais no documento de saída.

    Aqui a redação é deliberadamente sabotada: o CPF é confirmado, mas o PDF
    "de saída" é uma cópia do original. A validação precisa reprovar.
    """
    import shutil

    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    saida = pasta_saida / "nao_redigido.pdf"
    shutil.copy2(entrada, saida)

    candidato = Candidato(
        documento=entrada.name,
        pagina=0,
        categoria=Categoria.CPF,
        valor=CPF_ALFA,
        bboxes=[(0.0, 0.0, 100.0, 20.0)],
        status=Status.REDIGIDO,
    )
    validacao = validar_saida(saida, cfg, [candidato])
    assert validacao.residuais_conhecidos > 0
    assert validacao.veredito == Veredito.REPROVADO


def test_documento_limpo_e_aprovado(pasta_fixtures, pasta_saida, cfg):
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito == Veredito.APROVADO_TESTES
    assert relatorio.validacao.residuais_conhecidos == 0


def test_ocorrencias_pendentes_impedem_aprovacao(pasta_fixtures, pasta_saida, cfg):
    """Pendência deixada em aberto impede a aprovação.

    Com o padrão atual (tudo entra marcado para remoção) a pendência não
    aparece sozinha: é preciso que alguém a crie. O bloqueio, porém, continua
    valendo — e é ele que este teste protege.
    """
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    assert sessao.gerenciador.candidatos
    sessao.gerenciador.definir_status(
        sessao.gerenciador.candidatos[0].id, Status.PENDENTE
    )
    assert sessao.gerenciador.pendentes()
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito != Veredito.APROVADO_TESTES
    codigos = {r.codigo for r in relatorio.validacao.riscos}
    assert "OCORRENCIAS_PENDENTES" in codigos


def test_modo_classico_deixa_ocorrencias_pendentes(pasta_fixtures, pasta_saida, cfg):
    """Com `confirmar_por_padrao=False`, volta o fluxo de confirmação item a item."""
    cfg.deteccao.confirmar_por_padrao = False
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    assert sessao.gerenciador.pendentes(), "nada ficou aguardando decisão"
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito != Veredito.APROVADO_TESTES
    codigos = {r.codigo for r in relatorio.validacao.riscos}
    assert "OCORRENCIAS_PENDENTES" in codigos


def test_padrao_marca_tudo_para_remocao(pasta_fixtures, cfg):
    """O padrão é remover: nada entra aguardando decisão."""
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    candidatos = [c for c in sessao.gerenciador.candidatos if c.bboxes]
    assert candidatos
    assert all(c.status is Status.CONFIRMADO for c in candidatos), [
        (c.categoria.value, c.status.value) for c in candidatos
    ]
    assert sessao.gerenciador.pendentes() == []


def test_anexo_nao_tratado_impede_aprovacao(pasta_fixtures, pasta_saida, cfg):
    """Item 14 — anexo não suportado impede classificação como aprovado."""
    cfg.redacao.remover_anexos = False
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "14_anexo.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito != Veredito.APROVADO_TESTES
    codigos = {r.codigo for r in relatorio.validacao.riscos}
    assert "ANEXOS_RESIDUAIS" in codigos or "ANEXOS_MANTIDOS" in codigos


def test_assinatura_digital_impede_aprovacao(pasta_fixtures, pasta_saida, cfg):
    """Item 17 — documento assinado digitalmente não é aprovado automaticamente."""
    sessao = Sessao(cfg)
    entrada = pasta_fixtures / "17_assinatura.pdf"
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)
    confirmar_tudo(sessao)
    relatorio = sessao.processar(entrada, pasta_saida)
    assert relatorio.veredito != Veredito.APROVADO_TESTES


class TestDecisaoDeVeredito:
    def _resultado_limpo(self) -> ResultadoValidacao:
        r = ResultadoValidacao()
        r.abriu_corretamente = True
        return r

    def test_sem_pendencias_aprova(self, cfg):
        assert decidir_veredito(self._resultado_limpo(), cfg, []) == Veredito.APROVADO_TESTES

    def test_falha_critica_reprova(self, cfg):
        candidato = Candidato(
            documento="x.pdf",
            pagina=0,
            categoria=Categoria.CPF,
            valor="529.982.247-25",
            status=Status.FALHA_CRITICA,
        )
        assert decidir_veredito(self._resultado_limpo(), cfg, [candidato]) == Veredito.REPROVADO

    def test_aviso_sem_politica_exige_revisao(self, cfg):
        r = self._resultado_limpo()
        r.riscos.append(Risco("AVISO_X", "aviso qualquer", Severidade.AVISO))
        assert decidir_veredito(r, cfg, []) == Veredito.REVISAO_OBRIGATORIA

    def test_aviso_com_politica_permite_ressalva(self, cfg):
        cfg.permitir_aprovacao_com_ressalvas = True
        r = self._resultado_limpo()
        r.riscos.append(Risco("AVISO_X", "aviso qualquer", Severidade.AVISO))
        assert decidir_veredito(r, cfg, []) == Veredito.APROVADO_COM_RESSALVAS

    def test_bloqueio_critico_nunca_vira_ressalva(self, cfg):
        """Nenhuma configuração ignora um bloqueio crítico."""
        cfg.permitir_aprovacao_com_ressalvas = True
        r = self._resultado_limpo()
        r.riscos.append(
            Risco(
                "ARQUIVOS_INCORPORADOS",
                "anexo não analisado",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
        assert decidir_veredito(r, cfg, []) in (
            Veredito.REVISAO_OBRIGATORIA,
            Veredito.REPROVADO,
        )

    def test_pagina_sem_cobertura_impede_aprovacao(self, cfg):
        r = self._resultado_limpo()
        r.paginas_sem_cobertura.append(3)
        assert decidir_veredito(r, cfg, []) == Veredito.REVISAO_OBRIGATORIA

    def test_saida_ilegivel_reprova(self, cfg):
        r = ResultadoValidacao()
        r.abriu_corretamente = False
        assert decidir_veredito(r, cfg, []) == Veredito.REPROVADO


def test_riscos_da_inspecao_sao_herdados(pasta_fixtures, pasta_saida, cfg):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    doc = fitz.open(entrada)
    destino = pasta_saida / "copia.pdf"
    with doc:
        doc.save(destino)
    inspecao = Inspecao(arquivo=entrada.name)
    inspecao.riscos.append(
        Risco("TESTE_BLOQUEIO", "risco herdado", Severidade.CRITICO, bloqueia_aprovacao=True)
    )
    validacao = validar_saida(destino, cfg, [], inspecao_entrada=inspecao)
    assert any(r.codigo == "TESTE_BLOQUEIO" for r in validacao.riscos)
    assert validacao.veredito != Veredito.APROVADO_TESTES
