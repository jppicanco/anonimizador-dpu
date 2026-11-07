"""Coerência entre o que é detectado e o que fica no documento de saída.

Estes testes nasceram de um uso real que reprovou **os oito documentos**
processados. As causas não eram da redação em si — eram de detecção
incoerente, e a validação independente, corretamente, recusou aprovar.

Todos os dados aqui são fictícios.
"""

from __future__ import annotations

from anonimizador_dpu.core.brazilian_validators import validar_cnj
from anonimizador_dpu.core.config import Config
from anonimizador_dpu.core.entity_detector import (
    detectar,
    papeis_profissionais_no_texto,
)
from anonimizador_dpu.core.models import Categoria, Papel, Status
from anonimizador_dpu.core.pipeline import Sessao

PROCESSO = "5000446-50.2021.4.04.7204"


def test_numero_de_processo_quebrado_na_linha_e_detectado() -> None:
    """O OCR parte o número na mudança de linha; a ocorrência escapava.

    Escapando, ela não era redigida — mas o mesmo número, detectado em outro
    ponto, era. A validação então encontrava o número ainda legível na saída e
    reprovava o documento.
    """
    assert validar_cnj(PROCESSO)
    texto = f"PEDIDO DE UNIFORMIZAÇÃO Nº {PROCESSO[:8]}\n{PROCESSO[8:]}/SC"
    achados = [a for a in detectar(texto, Config()) if a.categoria is Categoria.PROCESSO_CNJ]
    assert achados, f"número partido não detectado em {texto!r}"


def test_numero_de_processo_inteiro_continua_detectado() -> None:
    achados = [
        a
        for a in detectar(f"Processo nº {PROCESSO}", Config())
        if a.categoria is Categoria.PROCESSO_CNJ
    ]
    assert len(achados) == 1


def test_profissional_e_reconhecido_pelo_rotulo() -> None:
    texto = "RELATOR: JUIZ FEDERAL Carlos Eduardo Pereira"
    assert papeis_profissionais_no_texto(texto, Config())


def test_mesma_pessoa_tratada_igual_em_todo_o_documento(
    pasta_fixtures, pasta_saida, cfg
) -> None:
    """A política de profissionais vale por pessoa, não por ocorrência.

    O mesmo nome aparece rotulado em um ponto ("RELATOR: JUIZ FEDERAL Fulano")
    e sem rótulo em outro ("assinado por Fulano"). Tratar as duas de forma
    diferente redige uma e deixa a outra: o nome continua legível, a redação
    não protege ninguém e a validação reprova.
    """
    import fitz

    nome = "Carlos Eduardo Pereira"
    entrada = pasta_saida / "decisao_com_magistrado.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((60, 80), f"RELATOR: JUIZ FEDERAL {nome}", fontsize=10)
    page.insert_text((60, 110), f"Documento assinado por {nome}.", fontsize=10)
    page.insert_text((60, 140), "REQUERENTE: Mariana Teste Alfa", fontsize=10)
    doc.save(entrada)
    doc.close()

    sessao = Sessao(cfg)
    sessao.inspecionar([entrada])
    sessao.analisar(entrada)

    do_magistrado = [
        c
        for c in sessao.gerenciador.candidatos
        if c.categoria is Categoria.NOME_PESSOA and nome.lower() in c.valor.lower()
    ]
    assert do_magistrado, "nenhuma ocorrência do magistrado foi registrada"
    assert all(c.status is Status.REJEITADO for c in do_magistrado), [
        (c.valor, c.status.value) for c in do_magistrado
    ]


def test_profissional_aparece_na_lista_em_vez_de_sumir(
    pasta_fixtures, pasta_saida, cfg
) -> None:
    """Ocorrência mantida por política fica visível e desmarcada.

    Sumir em silêncio escondia do revisor que aquele nome permaneceria no
    texto, e deixava a validação sem saber que a permanência era intencional.
    """
    texto = "Advogado: Carlos Eduardo Pereira, OAB/DF 1234."
    achados = [
        a
        for a in detectar(texto, Config(), aplicar_politica_profissionais=False)
        if a.categoria is Categoria.NOME_PESSOA
    ]
    assert achados
    assert achados[0].papel is Papel.ADVOGADO


def test_cargo_publico_nao_e_nome_de_pessoa() -> None:
    for expressao in (
        "CARGO DE AGENTE DE POLÍCIA FEDERAL",
        "Agente de Polícia",
        "o Delegado de Polícia Federal",
        "Professor de Matemática",
        "Analista Judiciário",
    ):
        achados = [
            a.valor for a in detectar(expressao, Config())
            if a.categoria is Categoria.NOME_PESSOA
        ]
        assert achados == [], f"{expressao!r} virou nome: {achados}"


def test_nome_de_doenca_nao_e_nome_de_pessoa() -> None:
    for expressao in (
        "Doença Pulmonar Obstrutiva Crônica",
        "Pulmonar Obstrutiva Crônica",
        "Insuficiência Renal Crônica",
        "Transtorno Depressivo Recorrente",
        "Esclerose Múltipla Progressiva",
    ):
        achados = [
            a.valor for a in detectar(expressao, Config())
            if a.categoria is Categoria.NOME_PESSOA
        ]
        assert achados == [], f"{expressao!r} virou nome: {achados}"


def test_fragmento_curto_nao_vira_localidade() -> None:
    """Ruído de OCR produzia localidades de duas letras."""
    achados = [
        a.valor for a in detectar("Vara de GA", Config())
        if a.categoria is Categoria.LOCALIDADE
    ]
    assert achados == [], achados
