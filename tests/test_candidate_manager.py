"""Testes do gerenciamento de candidatos (itens 5 e 24 dos testes obrigatórios)."""

from __future__ import annotations

from anonimizador_dpu.core.candidate_manager import GerenciadorCandidatos, chave_entidade
from anonimizador_dpu.core.models import Candidato, Categoria, Origem, Papel, Status


def _candidato(**kwargs) -> Candidato:
    base = dict(
        documento="doc1.pdf",
        pagina=0,
        categoria=Categoria.CPF,
        valor="529.982.247-25",
        bboxes=[(10.0, 10.0, 60.0, 20.0)],
        confianca=0.99,
    )
    base.update(kwargs)
    return Candidato(**base)


class TestChaveDeEntidade:
    def test_numeros_ignoram_pontuacao(self):
        assert chave_entidade(Categoria.CPF, "529.982.247-25") == chave_entidade(
            Categoria.CPF, "52998224725"
        )

    def test_nomes_usam_o_nome_completo(self):
        assert chave_entidade(Categoria.NOME_PESSOA, "Pessoa Teste Alfa") != chave_entidade(
            Categoria.NOME_PESSOA, "Pessoa Teste Beta"
        )

    def test_nome_normaliza_acentos_e_caixa(self):
        assert chave_entidade(Categoria.NOME_PESSOA, "José da Silva") == chave_entidade(
            Categoria.NOME_PESSOA, "JOSE DA SILVA"
        )


class TestPseudonimos:
    def test_mesma_entidade_recebe_o_mesmo_pseudonimo_entre_documentos(self):
        """Item 24 — consistência dos pseudônimos entre documentos."""
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(documento="doc1.pdf"),
                _candidato(documento="doc2.pdf", valor="52998224725"),
            ]
        )
        pseudonimos = {c.pseudonimo for c in g.candidatos}
        assert len(pseudonimos) == 1

    def test_entidades_distintas_recebem_pseudonimos_distintos(self):
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(valor="529.982.247-25"),
                _candidato(valor="111.444.777-35", pagina=1),
            ]
        )
        assert len({c.pseudonimo for c in g.candidatos}) == 2

    def test_papel_define_o_prefixo(self):
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(
                    categoria=Categoria.NOME_PESSOA,
                    valor="Pessoa Teste Alfa",
                    papel=Papel.TESTEMUNHA,
                )
            ]
        )
        assert g.candidatos[0].pseudonimo.startswith("[TESTEMUNHA_")

    def test_homonimos_podem_ser_separados(self):
        """Item 5 — pessoas diferentes com nomes iguais."""
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(
                    categoria=Categoria.NOME_PESSOA, valor="Pessoa Teste Alfa", pagina=0
                ),
                _candidato(
                    categoria=Categoria.NOME_PESSOA, valor="Pessoa Teste Alfa", pagina=1
                ),
            ]
        )
        assert len({c.pseudonimo for c in g.candidatos}) == 1
        novo = g.separar_entidade(g.candidatos[1].id, "testemunha homônima")
        assert novo
        assert g.candidatos[0].pseudonimo != g.candidatos[1].pseudonimo


class TestDeduplicacao:
    def test_texto_e_ocr_na_mesma_pagina_contam_uma_vez(self):
        """Evita contagem dupla da mesma ocorrência vista no texto e no OCR."""
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(origem=Origem.TEXTO, bboxes=[(1.0, 1.0, 2.0, 2.0)]),
                _candidato(origem=Origem.OCR, bboxes=[(3.0, 3.0, 4.0, 4.0)]),
            ]
        )
        assert len(g.candidatos) == 1
        unico = g.candidatos[0]
        assert unico.origem == Origem.TEXTO_E_OCR
        # Ambas as áreas são preservadas: a camada textual e a de imagem são
        # redigidas separadamente.
        assert len(unico.bboxes) == 2

    def test_paginas_diferentes_sao_ocorrencias_diferentes(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato(pagina=0), _candidato(pagina=1)])
        assert len(g.candidatos) == 2


class TestDecisoes:
    def test_aplicar_em_equivalentes(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato(pagina=p) for p in range(5)])
        g.definir_status(g.candidatos[0].id, Status.REJEITADO)
        alterados = g.aplicar_em_equivalentes(g.candidatos[0].id, Status.REJEITADO)
        assert alterados == 4
        assert all(c.status == Status.REJEITADO for c in g.candidatos)

    def test_confirmacao_automatica_respeita_limiar(self):
        g = GerenciadorCandidatos()
        g.adicionar(
            [
                _candidato(confianca=0.99, pagina=0),
                _candidato(confianca=0.60, pagina=1, valor="111.444.777-35"),
            ]
        )
        for c in g.candidatos:
            c.status = Status.DETECTADO
            c.requer_revisao = False
        confirmados = g.confirmar_automaticos(0.90)
        assert confirmados == 1

    def test_alteracao_de_categoria_recalcula_entidade(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato()])
        antigo = g.candidatos[0].pseudonimo
        g.definir_categoria(g.candidatos[0].id, Categoria.NIT_PIS_PASEP)
        assert g.candidatos[0].pseudonimo != antigo

    def test_inclusao_manual_ja_vem_confirmada(self):
        g = GerenciadorCandidatos()
        c = g.adicionar_manual(
            "doc1.pdf", 2, Categoria.REGIAO_MANUAL, "[região]", [(0.0, 0.0, 10.0, 10.0)]
        )
        assert c.status == Status.CONFIRMADO
        assert c.origem == Origem.MANUAL


class TestMinimizacaoDeDados:
    def test_serializacao_nao_expoe_o_valor_original(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato()])
        exportado = g.candidatos[0].to_dict()
        assert "529.982.247-25" not in str(exportado)
        assert exportado["valor_mascarado"].startswith("52")

    def test_tabela_de_reversao_exige_autorizacao(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato()])
        assert g.tabela_reversao(autorizado=False) == {}
        assert g.tabela_reversao(autorizado=True)

    def test_limpar_descarta_valores(self):
        g = GerenciadorCandidatos()
        g.adicionar([_candidato()])
        g.limpar()
        assert g.candidatos == []
        assert g.entidades == {}
