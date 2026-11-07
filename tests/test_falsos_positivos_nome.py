"""Falsos positivos de nome de pessoa relatados em uso real.

Todas as expressões abaixo foram marcadas como nome de pessoa pela heurística
original, em uma decisão da TNU sobre fornecimento de medicamento. Nenhuma
identifica ninguém: são títulos de seção, nomes de recurso, nomes de sistema e
vocabulário jurídico corrente.

O que a ferramenta deve remover é a identificação de pessoas — nome, endereço,
CPF e congêneres. Nome de medicamento, nome de recurso e expressão jurídica
não entram nisso.

Os nomes de pessoa usados aqui são fictícios.
"""

from __future__ import annotations

import pytest

from anonimizador_dpu.core.config import Config
from anonimizador_dpu.core.entity_detector import detectar
from anonimizador_dpu.core.models import Categoria, Papel

#: Expressões que **não** podem ser detectadas como nome de pessoa.
NAO_SAO_NOMES = [
    # relatadas pelo usuário
    "PODER JUDICIÁRIO",
    "Poder Judiciário",
    "PEDIDO DE UNIFORMIZAÇÃO",
    "Pedido de Uniformização",
    "PEDIDO DE UNIFORMIZAÇÃO DE INTERPRETAÇÃO DE LEI",
    "NAT JUS",
    "CONJUNTO PROBATÓRIO",
    "Conjunto Probatório",
    "FORNECIMENTO DE MEDICAMENTO NÃO INCORPORADO",
    "ELEMENTOS TÉCNICOS E PERICIAIS",
    "Elementos Técnicos e Periciais",
    "REEXAME DE PROVA",
    "Reexame de Prova",
    "VIA ELEITA",
    "DISPOSITIVO E TESE",
    "Dispositivo e Tese",
    # cabeçalhos do mesmo documento
    "CONSELHO DA JUSTIÇA FEDERAL",
    "TURMA NACIONAL DE UNIFORMIZAÇÃO",
    "Turma Nacional de Uniformização",
    "INSTITUTO NACIONAL DO SEGURO SOCIAL",
    "DESPACHO DECISÃO",
    "RELATÓRIO E VOTO",
    "FUNDAMENTAÇÃO JURÍDICA",
    # medicamentos e saúde
    "CLORIDRATO DE DULOXETINA",
    "SULFATO DE MORFINA",
    "PRINCÍPIO ATIVO",
    "PROTOCOLO CLÍNICO E DIRETRIZES TERAPÊUTICAS",
    "LAUDO MÉDICO PERICIAL",
    # vocabulário processual diverso
    "TRÂNSITO EM JULGADO",
    "COISA JULGADA",
    "AGRAVO INTERNO",
    "EMBARGOS DE DECLARAÇÃO",
    "HONORÁRIOS SUCUMBENCIAIS",
    "JUSTIÇA GRATUITA",
    "TUTELA DE URGÊNCIA",
    "AUXÍLIO DOENÇA",
    "BENEFÍCIO ASSISTENCIAL",
    "SALÁRIO MATERNIDADE",
    "APOSENTADORIA POR INVALIDEZ",
]

#: Nomes fictícios que **devem** continuar sendo detectados.
SAO_NOMES = [
    "Requerente: João da Silva Souza",
    "AUTOR: MARIA APARECIDA DOS SANTOS",
    "a testemunha Carlos Eduardo Pereira compareceu",
    "o depoimento de Ana Beatriz Oliveira foi colhido",
    "Nome: Pedro Henrique Almeida Costa",
    "REQUERIDO: JOSE CARLOS FERREIRA",
]


def _nomes_detectados(texto: str) -> list[str]:
    cfg = Config()
    return [
        a.valor
        for a in detectar(texto, cfg)
        if a.categoria is Categoria.NOME_PESSOA
    ]


@pytest.mark.parametrize("expressao", NAO_SAO_NOMES)
def test_expressao_comum_nao_vira_nome(expressao: str) -> None:
    achados = _nomes_detectados(expressao)
    assert achados == [], f"{expressao!r} foi tratada como nome: {achados}"


@pytest.mark.parametrize("expressao", NAO_SAO_NOMES)
def test_expressao_comum_dentro_de_frase(expressao: str) -> None:
    texto = f"Cuida-se de feito em que se discute {expressao}, conforme os autos."
    achados = _nomes_detectados(texto)
    assert achados == [], f"{expressao!r} foi tratada como nome: {achados}"


@pytest.mark.parametrize("texto", SAO_NOMES)
def test_nome_de_pessoa_continua_detectado(texto: str) -> None:
    assert _nomes_detectados(texto), f"nome não detectado em {texto!r}"


#: Nome de medicamento não identifica pessoa e não deve ser removido.
NAO_SAO_NOMES_MEDICAMENTOS = [
    "uso contínuo de Rivaroxabana Xarelto",
    "prescrição de Insulina Glargina",
    "medicamento Ozempic Semaglutida",
    "Dupilumabe Dupixent 300mg",
    "Cloridrato de Duloxetina 60mg",
    "Adalimumabe Humira seringa preenchida",
    "necessita de Nusinersena Spinraza",
    "tratamento com Pembrolizumabe Keytruda",
    "fornecimento de Canabidiol importado",
    "Cadastro Nacional de Pessoas Físicas",
]


@pytest.mark.parametrize("expressao", NAO_SAO_NOMES_MEDICAMENTOS)
def test_medicamento_nao_vira_nome(expressao: str) -> None:
    achados = _nomes_detectados(expressao)
    assert achados == [], f"{expressao!r} foi tratada como nome: {achados}"


def test_rotulo_processual_prevalece_sobre_contexto_de_medicamento() -> None:
    """Pessoa citada perto de remédio continua sendo pessoa."""
    texto = "o requerente Carlos Alberto Nogueira faz uso de Rivaroxabana."
    assert _nomes_detectados(texto) == ["Carlos Alberto Nogueira"]


#: Lugar identifica, e por isso é anonimizado — mas não é pessoa. Dar a ele um
#: papel processual produz pseudônimo errado: em "REQUERIDO: ESTADO DE SANTA
#: CATARINA" o requerido é o Estado, não a localidade.
LOCALIDADES = [
    ("REQUERIDO: ESTADO DE SANTA CATARINA", "SANTA CATARINA"),
    ("REQUERIDO: MUNICÍPIO DE NOVA VENEZA", "NOVA VENEZA"),
    ("contra acórdão da 3ª Turma Recursal de Santa Catarina", "Santa Catarina"),
    ("Comarca de Joinville", "Joinville"),
    ("natural de Belo Horizonte", "Belo Horizonte"),
    ("Seção Judiciária de Pernambuco", "Pernambuco"),
    ("residente em Porto Alegre", "Porto Alegre"),
    # Município de uma palavra só: a heurística de nomes exige duas, por isso
    # existe um detector próprio para o rótulo de localidade.
    ("Comarca de Criciúma", "Criciúma"),
    ("natural de Criciúma", "Criciúma"),
    ("Vara de Blumenau", "Blumenau"),
]

#: Sem rótulo ligando o lugar a alguém, não há pessoa a proteger — e
#: anonimizar ali só destrói o texto.
LOCALIDADES_GENERICAS = [
    "São Paulo, Minas Gerais e Rio de Janeiro são unidades federativas.",
    "A competência foi fixada conforme a legislação de Santa Catarina.",
    "O Tribunal Regional Federal da 4ª Região negou provimento.",
]


@pytest.mark.parametrize("texto", LOCALIDADES_GENERICAS)
def test_mencao_generica_a_lugar_nao_e_detectada(texto: str) -> None:
    achados = [
        (a.categoria.value, a.valor)
        for a in detectar(texto, Config())
        if a.categoria in (Categoria.LOCALIDADE, Categoria.NOME_PESSOA)
    ]
    assert achados == [], f"{texto!r} gerou {achados}"


@pytest.mark.parametrize("texto,esperado", LOCALIDADES)
def test_localidade_nao_e_pessoa(texto: str, esperado: str) -> None:
    achados = [
        a
        for a in detectar(texto, Config())
        if a.categoria in (Categoria.LOCALIDADE, Categoria.NOME_PESSOA)
    ]
    assert achados, f"nada detectado em {texto!r}"
    for a in achados:
        assert a.categoria is Categoria.LOCALIDADE, (
            f"{a.valor!r} classificado como {a.categoria.value}"
        )
    assert esperado in [a.valor for a in achados]


@pytest.mark.parametrize("texto,_esperado", LOCALIDADES)
def test_localidade_nao_recebe_papel_processual(texto: str, _esperado: str) -> None:
    """O pseudônimo de um lugar não pode ser [REQUERIDO_n] nem [REQUERENTE_n]."""
    for a in detectar(texto, Config()):
        if a.categoria is Categoria.LOCALIDADE:
            assert a.papel is None, f"{a.valor!r} recebeu papel {a.papel}"


def test_pessoa_com_rotulo_continua_recebendo_papel() -> None:
    """A separação não pode custar o papel de quem é mesmo parte."""
    achados = [
        a
        for a in detectar("REQUERENTE: AQUILINO TROMBIN", Config())
        if a.categoria is Categoria.NOME_PESSOA
    ]
    assert achados
    assert achados[0].papel is Papel.REQUERENTE


#: Palavras de logradouro que também são vocabulário jurídico corrente.
NAO_SAO_ENDERECOS = [
    "CONJUNTO PROBATÓRIO",
    "Conjunto Probatório",
    "CONJUNTO FÁTICO E PROBATÓRIO",
    "SETOR DE PERÍCIAS MÉDICAS",
    "Bloco de Constitucionalidade",
    "QUADRA DE ESPORTES",
    "LOTE DE PROCESSOS",
]

@pytest.mark.parametrize("expressao", NAO_SAO_ENDERECOS)
def test_expressao_juridica_nao_vira_endereco(expressao: str) -> None:
    cfg = Config()
    achados = [
        a.valor
        for a in detectar(expressao, cfg)
        if a.categoria is Categoria.ENDERECO
    ]
    assert achados == [], f"{expressao!r} foi tratada como endereço: {achados}"


@pytest.mark.parametrize(
    "texto", ["Rua das Palmeiras, 150", "Avenida Brasil, 2500", "Quadra 204, Conjunto B, Casa 15"]
)
def test_endereco_real_continua_detectado(texto: str) -> None:
    cfg = Config()
    achados = [a for a in detectar(texto, cfg) if a.categoria is Categoria.ENDERECO]
    assert achados, f"endereço não detectado em {texto!r}"


def test_documento_de_decisao_nao_gera_ruido() -> None:
    """Trecho sintético no estilo de uma decisão: só o nome deve sair."""
    texto = (
        "PODER JUDICIÁRIO\n"
        "CONSELHO DA JUSTIÇA FEDERAL\n"
        "TURMA NACIONAL DE UNIFORMIZAÇÃO\n\n"
        "PEDIDO DE UNIFORMIZAÇÃO DE INTERPRETAÇÃO DE LEI\n"
        "REQUERENTE: MARIA APARECIDA DOS SANTOS\n"
        "REQUERIDO: INSTITUTO NACIONAL DO SEGURO SOCIAL - INSS\n\n"
        "DESPACHO/DECISÃO\n\n"
        "Trata-se de incidente de uniformização nacional em que se discute o "
        "FORNECIMENTO DE MEDICAMENTO NÃO INCORPORADO às listas do SUS.\n"
        "O acórdão recorrido assentou que o CONJUNTO PROBATÓRIO, formado por "
        "ELEMENTOS TÉCNICOS E PERICIAIS e por nota do NAT JUS, seria "
        "insuficiente.\n"
        "A pretensão esbarra na vedação ao REEXAME DE PROVA, bem como na "
        "inadequação da VIA ELEITA.\n"
        "Ausente similitude entre o DISPOSITIVO E TESE do paradigma.\n"
    )
    achados = _nomes_detectados(texto)
    assert achados == ["MARIA APARECIDA DOS SANTOS"], achados
