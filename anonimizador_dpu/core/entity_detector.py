"""Detecção de dados pessoais por regras determinísticas, validadores e contexto.

Estratégia em camadas, toda executada localmente:

1. Expressões regulares específicas para padrões brasileiros;
2. validação de dígitos verificadores (eleva ou reduz a confiança);
3. análise do contexto imediato (rótulos como "CPF:", "Requerente:", "Nascido em");
4. heurística de nomes próprios em português, com lista de exclusões jurídicas;
5. opcionalmente, um modelo de reconhecimento de entidades instalado localmente
   (spaCy ou Presidio). A ausência desse modelo não impede o funcionamento.

Nenhuma etapa realiza chamadas de rede.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .audit_logger import obter_logger
from .brazilian_validators import (
    somente_digitos,
    validar_cartao_luhn,
    validar_cep,
    validar_cnh,
    validar_cnj,
    validar_cnpj,
    validar_cpf,
    validar_nb,
    validar_pis_pasep,
    validar_placa,
    validar_telefone,
    validar_titulo_eleitor,
)
from . import lexico_pt as lexico
from .config import Config
from .models import (
    BBox,
    Candidato,
    Categoria,
    Origem,
    PaginaTexto,
    Papel,
    Status,
)
from .text_extractor import bboxes_para_intervalo

_log = obter_logger("detector")


# ------------------------------------------------------------------ utilidades
def sem_acentos(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def _normalizar(texto: str) -> str:
    return sem_acentos(texto).lower()


@dataclass
class Achado:
    """Ocorrência bruta localizada em um texto, antes de virar candidato."""

    categoria: Categoria
    valor: str
    inicio: int
    fim: int
    confianca: float
    detector: str
    motivo: str = ""
    papel: Papel | None = None
    requer_revisao: bool = False


# ------------------------------------------------------------------- contexto
JANELA_CONTEXTO = 48

CONTEXTOS: dict[str, tuple[str, ...]] = {
    "cpf": ("cpf", "c.p.f", "cadastro de pessoa", "cadastro de pessoas"),
    "cnpj": ("cnpj", "c.n.p.j", "inscricao no cnpj"),
    "rg": (
        "rg",
        "r.g",
        "registro geral",
        "identidade",
        "carteira de identidade",
        "ssp",
        "ssp/",
        "doc. identidade",
    ),
    "cnh": ("cnh", "carteira nacional de habilitacao", "habilitacao", "registro cnh"),
    "titulo": ("titulo de eleitor", "titulo eleitoral", "inscricao eleitoral", "zona eleitoral"),
    "pis": ("pis", "pasep", "nit", "nis", "pis/pasep"),
    "nb": ("beneficio", "nb", "n.b", "numero do beneficio", "especie", "der"),
    "cep": ("cep", "c.e.p", "codigo postal"),
    # Afasta a hipótese de nome de pessoa: o que vem depois é remédio.
    "medicamento": (
        "medicamento",
        "medicamentos",
        "farmaco",
        "principio ativo",
        "substancia",
        "droga",
        "remedio",
        "uso de",
        "uso continuo de",
        "prescricao de",
        "prescrito",
        "receita de",
        "receituario",
        "dose de",
        "doses de",
        "comprimido",
        "comprimidos",
        "ampola",
        "ampolas",
        "frasco",
        "capsula",
        "capsulas",
        "seringa",
        "tratamento com",
        "terapia com",
        "administracao de",
        "fornecimento de",
        "fornecimento do",
    ),
    "telefone": ("telefone", "tel", "fone", "celular", "contato", "whatsapp", "ddd"),
    "conta": ("conta", "c/c", "conta corrente", "conta poupanca", "cc n", "conta n"),
    "agencia": ("agencia", "ag.", "ag ", "agencia n"),
    "pix": ("pix", "chave pix"),
    "cartao": ("cartao", "cartao de credito", "cartao de debito"),
    "nascimento": (
        "nascido",
        "nascida",
        "nascimento",
        "data de nascimento",
        "dn:",
        "d.n",
        "natural de",
    ),
    "passaporte": ("passaporte",),
    "placa": ("placa", "veiculo", "automovel"),
    "cid": ("cid", "cid-10", "cid 10", "diagnostico", "diagnostico de"),
    "matricula": ("matricula", "matr.", "registro funcional", "siape"),
    "protocolo": ("protocolo", "requerimento", "requerimento n", "procedimento"),
    "processo": ("processo", "autos", "acao", "n. do processo"),
}

#: Rótulos que antecedem nomes e indicam o papel processual da pessoa.
ROTULOS_PAPEL: tuple[tuple[str, Papel], ...] = (
    ("assistido", Papel.ASSISTIDO),
    ("assistida", Papel.ASSISTIDO),
    ("requerente", Papel.REQUERENTE),
    ("autor", Papel.REQUERENTE),
    ("autora", Papel.REQUERENTE),
    ("impetrante", Papel.REQUERENTE),
    ("exequente", Papel.REQUERENTE),
    ("requerido", Papel.REQUERIDO),
    ("requerida", Papel.REQUERIDO),
    ("reu", Papel.REQUERIDO),
    ("executado", Papel.REQUERIDO),
    ("testemunha", Papel.TESTEMUNHA),
    ("advogado", Papel.ADVOGADO),
    ("advogada", Papel.ADVOGADO),
    ("patrono", Papel.ADVOGADO),
    ("defensor", Papel.DEFENSOR),
    ("defensora", Papel.DEFENSOR),
    ("juiz", Papel.MAGISTRADO),
    ("juiza", Papel.MAGISTRADO),
    ("magistrado", Papel.MAGISTRADO),
    ("desembargador", Papel.MAGISTRADO),
    ("perito", Papel.PERITO),
    ("perita", Papel.PERITO),
    ("medico", Papel.PERITO),
    ("servidor", Papel.SERVIDOR),
    ("escrivao", Papel.SERVIDOR),
    ("genitora", Papel.FAMILIAR),
    ("genitor", Papel.FAMILIAR),
    ("mae", Papel.FAMILIAR),
    ("pai", Papel.FAMILIAR),
    ("conjuge", Papel.FAMILIAR),
    ("esposa", Papel.FAMILIAR),
    ("esposo", Papel.FAMILIAR),
    ("filho", Papel.FAMILIAR),
    ("filha", Papel.FAMILIAR),
    ("irmao", Papel.FAMILIAR),
    ("irma", Papel.FAMILIAR),
    ("dependente", Papel.FAMILIAR),
    ("menor", Papel.CRIANCA_ADOLESCENTE),
    ("adolescente", Papel.CRIANCA_ADOLESCENTE),
    ("crianca", Papel.CRIANCA_ADOLESCENTE),
    ("nome", None),  # rótulo genérico: eleva confiança sem definir papel
    ("sr.", None),
    ("sra.", None),
    ("dr.", None),
    ("dra.", None),
)

#: Papéis de profissionais, cuja anonimização é opcional conforme a política.
PAPEIS_PROFISSIONAIS = frozenset(
    {Papel.ADVOGADO, Papel.DEFENSOR, Papel.MAGISTRADO, Papel.PERITO, Papel.SERVIDOR}
)


def contexto_antes(texto: str, inicio: int, janela: int = JANELA_CONTEXTO) -> str:
    return _normalizar(texto[max(0, inicio - janela) : inicio])


def tem_contexto(texto: str, inicio: int, chave: str, janela: int = JANELA_CONTEXTO) -> bool:
    trecho = contexto_antes(texto, inicio, janela)
    return any(termo in trecho for termo in CONTEXTOS.get(chave, ()))


def papel_do_contexto(texto: str, inicio: int) -> tuple[Papel | None, bool]:
    """Infere o papel processual a partir do rótulo que antecede a ocorrência."""
    trecho = contexto_antes(texto, inicio, 64)
    melhor: tuple[int, Papel | None] = (-1, None)
    rotulado = False
    for rotulo, papel in ROTULOS_PAPEL:
        pos = trecho.rfind(rotulo)
        if pos >= 0:
            rotulado = True
            if pos > melhor[0]:
                melhor = (pos, papel)
    return melhor[1], rotulado


# -------------------------------------------------------- exclusões de nomes
_TERMOS_EXCLUIDOS_BRUTO = """
justica justico tribunal federal regional estadual superior supremo comarca vara
juizado turma camara secao secretaria cartorio foro gabinete ministerio publico
defensoria uniao estado municipio distrito advocacia geral procuradoria
instituto nacional seguro social previdencia caixa economica banco brasil
receita fazenda instituto brasileiro universidade faculdade hospital clinica
laboratorio prefeitura camara municipal assembleia legislativa senado congresso
republica presidencia governo conselho ordem advogados brasil oab seccional
processo autos acao peticao inicial contestacao sentenca acordao despacho decisao
recurso apelacao agravo embargos mandado seguranca habeas corpus liminar tutela
antecipada beneficio auxilio aposentadoria pensao salario maternidade doenca
invalidez assistencial loas prestacao continuada perícia pericia medica social
documento documentos anexo anexos certidao declaracao atestado laudo parecer
procuracao substabelecimento comprovante residencia extrato contracheque
janeiro fevereiro marco abril maio junho julho agosto setembro outubro novembro
dezembro segunda terca quarta quinta sexta sabado domingo
excelentissimo excelentissima senhor senhora doutor doutora meritissimo
nos termos artigo artigos lei leis decreto portaria resolucao sumula codigo
civil penal processual trabalho consumidor tributario administrativo
norte sul leste oeste centro brasilia sao paulo rio janeiro minas gerais bahia
parana santa catarina grande goias espirito santo mato grosso amazonas para
ceara pernambuco maranhao piaui alagoas sergipe paraiba potiche rondonia acre
roraima amapa tocantins federal republica federativa
total valor reais real data hora pagina paginas folha folhas numero
requerimento protocolo registro cadastro sistema portal consulta
rua avenida travessa alameda praca rodovia estrada quadra bloco lote conjunto
setor bairro apartamento apto casa edificio residencial condominio cidade
cpf cnpj rgs ssp sds detran denatran cnh nit pis pasep nis nbs cep ddd oab
inss dpu dpe pgf pgu agu tjs trf stf stj tst tse tre cnj cid uf ufs sus cras
creas aps der dib dcb pje eproc sei proc num obs fls doc docs anexo
termo audiencia ata assentada conciliacao instrucao julgamento sessao oficio
memorial alegacoes finais razoes contrarrazoes manifestacao oficio intimacao
citacao notificacao relatorio voto ementa acordam vistos relatados
"""
#: Mantido por compatibilidade: a lista efetiva agora é ``lexico_pt``, muito
#: mais ampla e organizada por tema.
TERMOS_EXCLUIDOS = lexico.TERMOS_NAO_PESSOA | frozenset(
    t for t in _TERMOS_EXCLUIDOS_BRUTO.split() if len(t) > 2
)

#: Conectores aceitos dentro de um nome composto.
CONECTORES_NOME = lexico.CONECTORES_NOME

_TOKEN_NOME = r"[A-ZÀ-ÖØ-Þ][a-zà-öø-ÿ'’]+"
#: Em texto integralmente maiúsculo, exige-se no mínimo três letras por token,
#: para não confundir siglas (RG, SSP, CPF) com partes de um nome.
_TOKEN_NOME_MAIUSCULO = r"[A-ZÀ-ÖØ-Þ]{3,}"
_CONECTOR = r"(?:de|da|do|das|dos|e|del|van|von)"

RE_NOME_CAPITALIZADO = re.compile(
    rf"\b{_TOKEN_NOME}(?:\s+(?:{_CONECTOR}\s+)?{_TOKEN_NOME})+\b"
)
RE_NOME_MAIUSCULO = re.compile(
    rf"\b{_TOKEN_NOME_MAIUSCULO}(?:\s+(?:{_CONECTOR.upper()}\s+)?{_TOKEN_NOME_MAIUSCULO})+\b"
)


# ------------------------------------------------------------------- padrões
RE_CPF = re.compile(r"\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\s\-]?\d{2}\b")
RE_CNPJ = re.compile(r"\b\d{2}[\.\s]?\d{3}[\.\s]?\d{3}[/\s]?\d{4}[\s\-]?\d{2}\b")
# O número pode vir quebrado na mudança de linha ("5000446-\n50.2021.4.04.7204"),
# e era isso que fazia uma ocorrência escapar da redação e reprovar o documento
# na validação. A permissividade é segura porque o dígito verificador do padrão
# CNJ é conferido em seguida.
RE_CNJ = re.compile(
    r"\b\d{7}\s*-?\s*\d{2}\s*\.?\s*\d{4}\s*\.?\s*\d\s*\.?\s*\d{2}\s*\.?\s*\d{4}\b"
)
RE_CEP = re.compile(r"\b\d{5}[\s\-]?\d{3}\b")
RE_TELEFONE = re.compile(
    r"(?:\+?55[\s\-]?)?(?:\(\d{2}\)|\b\d{2})[\s\-\.]?9?\d{4}[\s\-\.]?\d{4}\b"
)
RE_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]{2,}\b")
RE_NUM_11 = re.compile(r"\b\d{3}[\.\s]?\d{5}[\.\s]?\d{2}[\s\-]?\d\b|\b\d{11}\b")
RE_NUM_12 = re.compile(r"\b\d{4}[\s\.]?\d{4}[\s\.]?\d{4}\b|\b\d{12}\b")
RE_NUM_10 = re.compile(r"\b\d{3}[\.\s]?\d{3}[\.\s]?\d{3}[\s\-]?\d\b|\b\d{10}\b")
RE_RG = re.compile(r"\b\d{1,2}[\.\s]?\d{3}[\.\s]?\d{3}[\s\-]?[\dxX]?\b")
RE_PASSAPORTE = re.compile(r"\b[A-Z]{2}\d{6}\b")
RE_PLACA = re.compile(r"\b[A-Z]{3}[\s\-]?\d[A-Z0-9]\d{2}\b")
RE_CARTAO = re.compile(r"\b\d{4}[\s\.\-]?\d{4}[\s\.\-]?\d{4}[\s\.\-]?\d{1,7}\b")
RE_CID = re.compile(r"\b[A-TV-Z]\d{2}(?:\.\d)?\b")
RE_DATA = re.compile(r"\b(\d{1,2})[/\.\-](\d{1,2})[/\.\-](\d{2,4})\b")
RE_URL = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
RE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
RE_CONTA = re.compile(r"\b\d{3,8}[\-\s]?[\dxX]\b")
RE_AGENCIA = re.compile(r"\b\d{3,5}[\-\s]?[\dxX]?\b")

#: Palavras de logradouro que, sozinhas, já indicam endereço.
_LOGRADOURO_FORTE = (
    r"Rua|R\.|Avenida|Av\.|Travessa|Alameda|Praça|Praca|Rodovia|Estrada|"
    r"Q[NSIE]{1,2}|SQN|SQS|SHIS|SHIN|CLN|CLS"
)
#: Palavras ambíguas: também são vocabulário jurídico corrente
#: ("CONJUNTO PROBATÓRIO", "SETOR DE PERÍCIAS", "BLOCO DE CONSTITUCIONALIDADE").
#: Só valem como endereço quando há número no trecho.
_LOGRADOURO_AMBIGUO = r"Quadra|Conjunto|Setor|Lote|Bloco|Chácara|Chacara"

RE_ENDERECO = re.compile(
    rf"\b(?:{_LOGRADOURO_FORTE}|{_LOGRADOURO_AMBIGUO})"
    r"\s+[^\n,;]{2,60}(?:,\s*(?:n[ºo°\.]?\s*)?\d{1,6}[^\n;]{0,40})?",
    re.IGNORECASE,
)
RE_LOGRADOURO_AMBIGUO = re.compile(rf"^(?:{_LOGRADOURO_AMBIGUO})\b", re.IGNORECASE)

TOKENS_URL_SENSIVEL = (
    "token",
    "key=",
    "senha",
    "password",
    "cpf=",
    "id=",
    "chave",
    "acesso",
    "auth",
)


# ---------------------------------------------------------- detector por regra
def _janela_valor(texto: str, m: re.Match) -> str:
    return m.group(0).strip()


def _detectar_documentos(texto: str) -> list[Achado]:
    achados: list[Achado] = []

    # CPF -------------------------------------------------------------
    for m in RE_CPF.finditer(texto):
        valor = _janela_valor(texto, m)
        tem_ctx = tem_contexto(texto, m.start(), "cpf")
        if validar_cpf(valor):
            pontuado = bool(re.search(r"[.\-]", valor))
            conf = 0.99 if (tem_ctx or pontuado) else 0.88
            achados.append(
                Achado(
                    Categoria.CPF,
                    valor,
                    m.start(),
                    m.end(),
                    conf,
                    "regex+dv",
                    "CPF com dígitos verificadores válidos"
                    + (" e rótulo de contexto" if tem_ctx else ""),
                )
            )
        elif tem_ctx:
            achados.append(
                Achado(
                    Categoria.CPF,
                    valor,
                    m.start(),
                    m.end(),
                    0.72,
                    "regex+contexto",
                    "Número rotulado como CPF, mas com dígito verificador inválido "
                    "(possível erro de digitação ou de OCR).",
                    requer_revisao=True,
                )
            )

    # CNPJ ------------------------------------------------------------
    for m in RE_CNPJ.finditer(texto):
        valor = _janela_valor(texto, m)
        if validar_cnpj(valor):
            achados.append(
                Achado(
                    Categoria.CNPJ,
                    valor,
                    m.start(),
                    m.end(),
                    0.95,
                    "regex+dv",
                    "CNPJ com dígitos verificadores válidos",
                )
            )

    # Processo CNJ ----------------------------------------------------
    for m in RE_CNJ.finditer(texto):
        valor = _janela_valor(texto, m)
        if validar_cnj(valor):
            achados.append(
                Achado(
                    Categoria.PROCESSO_CNJ,
                    valor,
                    m.start(),
                    m.end(),
                    0.98,
                    "regex+dv",
                    "Número de processo no padrão CNJ com dígito verificador válido",
                )
            )
        else:
            achados.append(
                Achado(
                    Categoria.PROCESSO_CNJ,
                    valor,
                    m.start(),
                    m.end(),
                    0.70,
                    "regex",
                    "Número no formato CNJ com dígito verificador inválido",
                    requer_revisao=True,
                )
            )

    # Título de eleitor ----------------------------------------------
    for m in RE_NUM_12.finditer(texto):
        valor = _janela_valor(texto, m)
        if not validar_titulo_eleitor(valor):
            continue
        tem_ctx = tem_contexto(texto, m.start(), "titulo")
        achados.append(
            Achado(
                Categoria.TITULO_ELEITOR,
                valor,
                m.start(),
                m.end(),
                0.93 if tem_ctx else 0.65,
                "regex+dv",
                "Título de eleitor válido" + ("" if tem_ctx else " (sem rótulo de contexto)"),
                requer_revisao=not tem_ctx,
            )
        )

    # PIS/PASEP/NIT e CNH (ambos com 11 dígitos) ----------------------
    for m in RE_NUM_11.finditer(texto):
        valor = _janela_valor(texto, m)
        if validar_cpf(valor):
            continue  # já tratado como CPF
        ctx_pis = tem_contexto(texto, m.start(), "pis")
        ctx_cnh = tem_contexto(texto, m.start(), "cnh")
        if ctx_pis and validar_pis_pasep(valor):
            achados.append(
                Achado(
                    Categoria.NIT_PIS_PASEP,
                    valor,
                    m.start(),
                    m.end(),
                    0.95,
                    "regex+dv+contexto",
                    "PIS/PASEP/NIT válido com rótulo de contexto",
                )
            )
        elif ctx_cnh and validar_cnh(valor):
            achados.append(
                Achado(
                    Categoria.CNH,
                    valor,
                    m.start(),
                    m.end(),
                    0.92,
                    "regex+dv+contexto",
                    "Registro de CNH válido com rótulo de contexto",
                )
            )
        elif ctx_pis or ctx_cnh:
            achados.append(
                Achado(
                    Categoria.NIT_PIS_PASEP if ctx_pis else Categoria.CNH,
                    valor,
                    m.start(),
                    m.end(),
                    0.68,
                    "regex+contexto",
                    "Número rotulado como identificador pessoal, sem validação de dígito",
                    requer_revisao=True,
                )
            )

    # Benefício (NB) --------------------------------------------------
    for m in RE_NUM_10.finditer(texto):
        valor = _janela_valor(texto, m)
        if not tem_contexto(texto, m.start(), "nb"):
            continue
        valido = validar_nb(valor)
        achados.append(
            Achado(
                Categoria.BENEFICIO_NB,
                valor,
                m.start(),
                m.end(),
                0.90 if valido else 0.68,
                "regex+contexto" + ("+dv" if valido else ""),
                "Número de benefício rotulado no texto"
                + (" com dígito verificador válido" if valido else ""),
                requer_revisao=not valido,
            )
        )

    # RG --------------------------------------------------------------
    for m in RE_RG.finditer(texto):
        valor = _janela_valor(texto, m)
        if not tem_contexto(texto, m.start(), "rg", janela=32):
            continue
        digitos = somente_digitos(valor)
        if not 5 <= len(digitos) <= 10:
            continue
        # Um número rotulado como CEP não é RG; um CPF já foi tratado acima.
        if validar_cpf(valor) or tem_contexto(texto, m.start(), "cep", janela=16):
            continue
        achados.append(
            Achado(
                Categoria.RG,
                valor,
                m.start(),
                m.end(),
                0.78,
                "regex+contexto",
                "Número de documento de identidade rotulado no texto. Não há padrão "
                "nacional único de RG: a identificação depende do contexto.",
                requer_revisao=True,
            )
        )

    # Passaporte ------------------------------------------------------
    for m in RE_PASSAPORTE.finditer(texto):
        if tem_contexto(texto, m.start(), "passaporte"):
            achados.append(
                Achado(
                    Categoria.PASSAPORTE,
                    _janela_valor(texto, m),
                    m.start(),
                    m.end(),
                    0.88,
                    "regex+contexto",
                    "Número de passaporte rotulado no texto",
                )
            )

    return achados


def _detectar_contato(texto: str) -> list[Achado]:
    achados: list[Achado] = []

    for m in RE_EMAIL.finditer(texto):
        achados.append(
            Achado(
                Categoria.EMAIL,
                _janela_valor(texto, m),
                m.start(),
                m.end(),
                0.97,
                "regex",
                "Endereço de e-mail",
            )
        )

    for m in RE_CEP.finditer(texto):
        valor = _janela_valor(texto, m)
        if not validar_cep(valor):
            continue
        tem_ctx = tem_contexto(texto, m.start(), "cep")
        com_hifen = "-" in valor
        if not (tem_ctx or com_hifen):
            continue
        achados.append(
            Achado(
                Categoria.CEP,
                valor,
                m.start(),
                m.end(),
                0.93 if tem_ctx else 0.76,
                "regex" + ("+contexto" if tem_ctx else ""),
                "CEP no formato brasileiro",
                requer_revisao=not tem_ctx,
            )
        )

    for m in RE_TELEFONE.finditer(texto):
        valor = _janela_valor(texto, m)
        if not validar_telefone(valor):
            continue
        tem_ctx = tem_contexto(texto, m.start(), "telefone")
        com_formatacao = bool(re.search(r"[()\-]", valor))
        if not (tem_ctx or com_formatacao):
            continue
        achados.append(
            Achado(
                Categoria.TELEFONE,
                valor,
                m.start(),
                m.end(),
                0.92 if tem_ctx else 0.74,
                "regex+ddd",
                "Telefone com DDD atribuído no Plano Nacional de Numeração",
                requer_revisao=not tem_ctx,
            )
        )

    for m in RE_ENDERECO.finditer(texto):
        valor = _janela_valor(texto, m).rstrip(" .;,")
        if len(valor) < 8:
            continue
        # Palavra de logradouro ambígua ("Conjunto", "Setor", "Bloco") também é
        # vocabulário jurídico corrente. Só vale como endereço com número no
        # trecho e sem termo jurídico logo em seguida — do contrário,
        # "CONJUNTO PROBATÓRIO" viraria endereço.
        #
        # A restrição não se aplica às palavras fortes (Rua, Avenida…), porque
        # nome de logradouro usa palavra comum o tempo todo: "Avenida Brasil".
        if RE_LOGRADOURO_AMBIGUO.match(valor):
            if not re.search(r"\d", valor):
                continue
            seguinte = _significativos(valor)[1:2]
            if seguinte and lexico.e_vocabulario_comum(seguinte[0]):
                continue
        achados.append(
            Achado(
                Categoria.ENDERECO,
                valor,
                m.start(),
                m.start() + len(valor),
                0.78,
                "regex",
                "Logradouro identificado por palavra-chave de endereço",
                requer_revisao=True,
            )
        )

    return achados


def _detectar_financeiro(texto: str) -> list[Achado]:
    achados: list[Achado] = []

    for m in RE_CARTAO.finditer(texto):
        valor = _janela_valor(texto, m)
        if validar_cartao_luhn(valor) and len(somente_digitos(valor)) >= 13:
            achados.append(
                Achado(
                    Categoria.CARTAO,
                    valor,
                    m.start(),
                    m.end(),
                    0.90,
                    "regex+luhn",
                    "Número compatível com cartão (algoritmo de Luhn)",
                )
            )

    for m in RE_CONTA.finditer(texto):
        if tem_contexto(texto, m.start(), "conta", janela=24):
            achados.append(
                Achado(
                    Categoria.CONTA_BANCARIA,
                    _janela_valor(texto, m),
                    m.start(),
                    m.end(),
                    0.82,
                    "regex+contexto",
                    "Número rotulado como conta bancária",
                    requer_revisao=True,
                )
            )

    for m in RE_AGENCIA.finditer(texto):
        if tem_contexto(texto, m.start(), "agencia", janela=20):
            achados.append(
                Achado(
                    Categoria.AGENCIA_BANCARIA,
                    _janela_valor(texto, m),
                    m.start(),
                    m.end(),
                    0.80,
                    "regex+contexto",
                    "Número rotulado como agência bancária",
                    requer_revisao=True,
                )
            )

    for m in RE_UUID.finditer(texto):
        if tem_contexto(texto, m.start(), "pix", janela=40):
            achados.append(
                Achado(
                    Categoria.CHAVE_PIX,
                    _janela_valor(texto, m),
                    m.start(),
                    m.end(),
                    0.92,
                    "regex+contexto",
                    "Chave Pix aleatória (UUID) rotulada no texto",
                )
            )

    return achados


def _detectar_outros(texto: str) -> list[Achado]:
    achados: list[Achado] = []

    for m in RE_PLACA.finditer(texto):
        valor = _janela_valor(texto, m)
        tem_ctx = tem_contexto(texto, m.start(), "placa")
        if validar_placa(valor.replace(" ", "")) or tem_ctx:
            achados.append(
                Achado(
                    Categoria.PLACA_VEICULO,
                    valor,
                    m.start(),
                    m.end(),
                    0.88 if tem_ctx else 0.72,
                    "regex",
                    "Placa de veículo",
                    requer_revisao=not tem_ctx,
                )
            )

    for m in RE_URL.finditer(texto):
        valor = _janela_valor(texto, m)
        if any(t in valor.lower() for t in TOKENS_URL_SENSIVEL):
            achados.append(
                Achado(
                    Categoria.URL_COM_TOKEN,
                    valor,
                    m.start(),
                    m.end(),
                    0.85,
                    "regex",
                    "URL contendo parâmetro potencialmente identificador",
                )
            )

    for m in RE_CID.finditer(texto):
        if tem_contexto(texto, m.start(), "cid", janela=24):
            achados.append(
                Achado(
                    Categoria.DADO_SAUDE,
                    _janela_valor(texto, m),
                    m.start(),
                    m.end(),
                    0.86,
                    "regex+contexto",
                    "Código CID rotulado no texto (dado pessoal sensível)",
                )
            )

    for m in RE_DATA.finditer(texto):
        if not tem_contexto(texto, m.start(), "nascimento", janela=40):
            continue
        dia, mes, ano = m.groups()
        try:
            d, mth, y = int(dia), int(mes), int(ano)
        except ValueError:  # pragma: no cover
            continue
        if not (1 <= d <= 31 and 1 <= mth <= 12):
            continue
        achados.append(
            Achado(
                Categoria.DATA_NASCIMENTO,
                _janela_valor(texto, m),
                m.start(),
                m.end(),
                0.90,
                "regex+contexto",
                "Data rotulada como data de nascimento",
            )
        )

    return achados


# ----------------------------------------------------------- nomes próprios
#: Terminações verbais frequentes em português. Servem para evitar que a
#: palavra que abre uma frase ("Compareceu", "Declarou", "Trata-se") seja
#: confundida com o primeiro nome de uma pessoa, já que ela também aparece com
#: inicial maiúscula.
SUFIXOS_VERBAIS = (
    "ou",
    "eu",
    "iu",
    "aram",
    "eram",
    "iram",
    "ram",
    "rem",
    "ndo",
    "ado",
    "ada",
    "ados",
    "adas",
    "ido",
    "ida",
    "idos",
    "idas",
    "ava",
    "avam",
    "iam",
    "sse",
    "ssem",
    "mos",
    "-se",
)

#: Caracteres que indicam o encerramento da frase anterior.
_FIM_DE_FRASE = ".!?:;\n"


def _inicio_de_frase(texto: str, posicao: int) -> bool:
    i = posicao - 1
    while i >= 0 and texto[i] in " \t":
        i -= 1
    return i < 0 or texto[i] in _FIM_DE_FRASE


def _ajustar_inicio_de_frase(texto: str, inicio: int, valor: str) -> tuple[int, str] | None:
    """Descarta o verbo que abre a frase, quando ele precede o nome.

    Devolve ``(novo_inicio, novo_valor)`` ou ``None`` quando nada sobra.
    """
    if not _inicio_de_frase(texto, inicio):
        return inicio, valor
    partes = valor.split()
    if not partes:
        return None
    primeiro = _normalizar(partes[0])
    if not primeiro.endswith(SUFIXOS_VERBAIS):
        return inicio, valor
    restante = valor[len(partes[0]) :]
    deslocamento = len(valor) - len(restante.lstrip())
    novo_valor = restante.lstrip()
    if len([p for p in novo_valor.split() if _normalizar(p) not in CONECTORES_NOME]) < 2:
        return None
    return inicio + deslocamento, novo_valor


def _rotulo_de_localidade_antes(texto: str, inicio: int) -> bool:
    """Há "ESTADO DE", "MUNICÍPIO DE", "COMARCA DE"… imediatamente antes?"""
    anterior = _normalizar(texto[max(0, inicio - 40) : inicio])
    anterior = re.sub(r"[\s\.:;,\-–—]+$", " ", anterior + " ")
    return any(anterior.endswith(r + " ") for r in lexico.ROTULOS_LOCALIDADE)


#: Rótulo de localidade seguido do nome do lugar. Existe à parte da heurística
#: de nomes porque esta exige duas palavras, e município costuma ter uma só —
#: "Comarca de Criciúma".
#: Nome de lugar: palavras capitalizadas, unidas direto ("Santa Catarina") ou
#: por conector ("Rio de Janeiro"). Sem `IGNORECASE` — a maiúscula é o sinal.
_NOME_LUGAR = (
    r"(?P<lugar>[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’]+"
    r"(?:\s+(?:(?:de|da|do|das|dos|e)\s+)?[A-ZÀ-ÖØ-Þ][\wÀ-ÖØ-öø-ÿ'’]+)*)"
)

RE_LOCALIDADE_ROTULADA = re.compile(
    r"\b(?:[Ee]stado|[Mm]unic[íi]pio|[Cc]omarca|[Cc]idade|"
    r"[Ss]e[çc][ãa]o\s+[Jj]udici[áa]ria|[Ss]ubse[çc][ãa]o\s+[Jj]udici[áa]ria|"
    r"[Tt]urma\s+[Rr]ecursal|[Ff]oro|[Vv]ara|[Rr]egi[ãa]o)"
    r"\s+d[eoa]s?\s+" + _NOME_LUGAR
)

#: Expressões de origem e residência, que ligam o lugar a uma pessoa.
RE_LOCALIDADE_PESSOAL = re.compile(
    r"\b(?:[Nn]atural\s+d[eoa]s?|[Nn]ascid[oa]\s+em|[Rr]esidente\s+em|"
    r"[Dd]omiciliad[oa]\s+em|[Rr]eside\s+em|[Mm]ora\s+em|"
    r"[Oo]riund[oa]\s+d[eoa]s?|[Pp]rocedente\s+d[eoa]s?)\s+" + _NOME_LUGAR
)


def _detectar_localidades(texto: str) -> list[Achado]:
    """Cidade, estado ou comarca indicados por rótulo explícito.

    O lugar identifica e por isso é anonimizável, mas **não é pessoa**: não
    recebe papel processual nem pseudônimo de parte.
    """
    achados: list[Achado] = []
    vistos: set[tuple[int, int]] = set()
    for regex, confianca in ((RE_LOCALIDADE_ROTULADA, 0.76), (RE_LOCALIDADE_PESSOAL, 0.80)):
        for m in regex.finditer(texto):
            inicio, fim = m.span("lugar")
            if (inicio, fim) in vistos:
                continue
            valor = m.group("lugar").strip()
            if len(valor) < 3 or lexico.e_vocabulario_comum(valor.split()[0]):
                continue
            vistos.add((inicio, fim))
            achados.append(
                Achado(
                    Categoria.LOCALIDADE,
                    valor,
                    inicio,
                    inicio + len(valor),
                    confianca,
                    "localidade",
                    "Cidade, estado ou comarca indicada por rótulo",
                    requer_revisao=True,
                )
            )
    return achados


def _sufixo_de_localidade(valor: str) -> tuple[int, str] | None:
    """Maior unidade federativa ou capital que encerra o trecho."""
    normal = lexico.normalizar(valor)
    if len(normal) != len(valor):  # o mapa de posições tem de ser confiável
        return None
    fim_util = len(normal.rstrip(".,;:()"))
    melhor: tuple[int, str] | None = None
    for local in lexico.LOCALIDADES_CONHECIDAS:
        pos = normal.rfind(local, 0, fim_util)
        if pos < 0 or pos + len(local) != fim_util:
            continue
        if pos and normal[pos - 1] != " ":
            continue
        if melhor is None or len(local) > len(melhor[1]):
            melhor = (pos, valor[pos : pos + len(local)])
    return melhor


def localidade_em(
    texto: str, inicio: int, valor: str, aparado: tuple[int, str] | None
) -> tuple[int, str] | None:
    """Reconhece um lugar na ocorrência. Devolve ``(recuo, nome do lugar)``.

    **Exige rótulo de localidade** antes do trecho — "ESTADO DE", "COMARCA DE",
    "natural de". Um nome de estado solto não basta: numa frase como "São Paulo
    e Minas Gerais são unidades federativas" não há pessoa alguma a proteger, e
    anonimizar ali só destrói o texto.

    A lista de unidades federativas serve para **delimitar** o trecho, não para
    detectá-lo. Isso importa porque o nome do estado também consta do léxico
    geral e desapareceria no aparo de vocabulário: "Seção Judiciária de
    Pernambuco" acabaria em nada.
    """
    sufixo = _sufixo_de_localidade(valor)
    if sufixo is not None and _rotulo_de_localidade_antes(texto, inicio + sufixo[0]):
        return sufixo
    if aparado is not None:
        recuo, trecho = aparado
        if trecho and _rotulo_de_localidade_antes(texto, inicio + recuo):
            interno = _sufixo_de_localidade(trecho)
            if interno is not None:
                return recuo + interno[0], interno[1]
            return recuo, trecho
    return None


#: Acima deste número de palavras significativas, sem nenhuma evidência de
#: pessoa, trata-se quase sempre de um título de seção, não de um nome.
MAX_TOKENS_SEM_EVIDENCIA = 4


@dataclass
class AvaliacaoNome:
    """Resultado da análise de uma sequência candidata a nome de pessoa."""

    aceito: bool
    confianca: float = 0.0
    motivo: str = ""


def _significativos(candidato: str) -> list[str]:
    tokens = [t for t in re.split(r"\s+", candidato.strip()) if t]
    return [t for t in tokens if _normalizar(t) not in CONECTORES_NOME]


def aparar_vocabulario(valor: str) -> tuple[int, str]:
    """Remove vocabulário comum colado às bordas da sequência.

    A expressão de nome atravessa a quebra de linha, de modo que um nome no
    fim de uma linha pode arrastar o rótulo da linha seguinte
    (``"MARIA ... DOS SANTOS\\nREQUERIDO"``). Aparar a borda preserva o nome;
    rejeitar o candidato inteiro o perderia.

    Devolve ``(deslocamento, novo_valor)``.
    """
    tokens = [t for t in re.split(r"(\s+)", valor) if t]
    # Índices das palavras (ignorando os separadores capturados).
    palavras = [i for i, t in enumerate(tokens) if not t.isspace()]

    def descartavel(indice: int) -> bool:
        token = tokens[indice]
        return lexico.normalizar(token).strip(".,;:()") not in lexico.CONECTORES_NOME and (
            lexico.e_vocabulario_comum(token)
        )

    inicio, fim = 0, len(palavras)
    while inicio < fim and descartavel(palavras[inicio]):
        inicio += 1
    while fim > inicio and descartavel(palavras[fim - 1]):
        fim -= 1
    # Conectores soltos nas pontas também saem ("de Silva" → "Silva").
    while inicio < fim and lexico.normalizar(tokens[palavras[inicio]]) in lexico.CONECTORES_NOME:
        inicio += 1
    while fim > inicio and lexico.normalizar(tokens[palavras[fim - 1]]) in lexico.CONECTORES_NOME:
        fim -= 1

    if inicio >= fim:
        return 0, ""
    primeiro, ultimo = palavras[inicio], palavras[fim - 1]
    deslocamento = sum(len(t) for t in tokens[:primeiro])
    novo = "".join(tokens[primeiro : ultimo + 1])
    return deslocamento, novo


def avaliar_nome(
    candidato: str,
    rotulado: bool,
    caixa_alta: bool,
    contexto_medicamento: bool = False,
) -> AvaliacaoNome:
    """Decide se a sequência identifica uma pessoa, e com que confiança.

    A regra é de **evidência positiva**: não basta estar em maiúsculas. Peça
    judicial é cheia de títulos ("PODER JUDICIÁRIO", "REEXAME DE PROVA") que a
    heurística antiga tomava por nome. Ver ``core/lexico_pt.py``.
    """
    significativos = _significativos(candidato)
    if len(significativos) < 2:
        return AvaliacaoNome(False, motivo="menos de duas palavras")

    # "uso contínuo de Rivaroxabana Xarelto" é remédio, não pessoa. O rótulo
    # processual prevalece, para o caso de "o requerente X tomava o remédio".
    if contexto_medicamento and not rotulado:
        return AvaliacaoNome(False, motivo="precedido de contexto de medicamento")

    # Uma unidade federativa ou capital nunca é pessoa, ainda que uma de suas
    # palavras seja prenome — "Santa Catarina", "São Paulo". Sem rótulo de
    # localidade por perto, não é anonimizada: é só menção genérica a lugar.
    if lexico.normalizar(candidato).strip(".,;:()") in lexico.LOCALIDADES_CONHECIDAS:
        return AvaliacaoNome(False, motivo="unidade federativa ou capital")

    for token in significativos:
        if len(_normalizar(token).strip(".,;:()")) < 2:
            return AvaliacaoNome(False, motivo="palavra curta demais")
        if lexico.e_vocabulario_comum(token):
            return AvaliacaoNome(
                False, motivo=f"vocabulário comum: {token}"
            )

    primeiro = lexico.normalizar(significativos[0]).strip(".,;:()")
    prenome_inicial = primeiro in lexico.PRENOMES
    algum_prenome = any(
        lexico.normalizar(t).strip(".,;:()") in lexico.PRENOMES for t in significativos
    )
    algum_sobrenome = any(
        lexico.normalizar(t).strip(".,;:()") in lexico.SOBRENOMES for t in significativos
    )

    pontos = 0
    if rotulado:
        pontos += 3
    if prenome_inicial:
        pontos += 3
    elif algum_prenome:
        pontos += 2
    if algum_sobrenome:
        pontos += 2

    # Texto inteiramente em caixa alta é, em peça judicial, muito mais vezes
    # título de seção do que nome. Só passa com evidência de pessoa.
    if caixa_alta and pontos < 2:
        return AvaliacaoNome(
            False, motivo="caixa alta sem rótulo processual nem nome conhecido"
        )

    if pontos == 0 and len(significativos) > MAX_TOKENS_SEM_EVIDENCIA:
        return AvaliacaoNome(False, motivo="expressão longa sem evidência de pessoa")

    conf = 0.48
    if rotulado:
        conf += 0.28
    if prenome_inicial:
        conf += 0.18
    elif algum_prenome:
        conf += 0.12
    if algum_sobrenome:
        conf += 0.10
    if len(significativos) >= 3:
        conf += 0.04

    detalhes = []
    if rotulado:
        detalhes.append("rótulo processual")
    if prenome_inicial or algum_prenome:
        detalhes.append("prenome conhecido")
    if algum_sobrenome:
        detalhes.append("sobrenome conhecido")
    motivo = "Sequência de nomes próprios"
    if detalhes:
        motivo += " (" + ", ".join(detalhes) + ")"

    return AvaliacaoNome(True, min(conf, 0.95), motivo)


def _detectar_nomes(texto: str, cfg: Config) -> list[Achado]:
    if not cfg.deteccao.detectar_nomes_heuristica:
        return []
    achados: list[Achado] = []
    vistos: set[tuple[int, int]] = set()

    for regex, caixa_alta, detector in (
        (RE_NOME_CAPITALIZADO, False, "heuristica_nome"),
        (RE_NOME_MAIUSCULO, True, "heuristica_nome_maiusculo"),
    ):
        for m in regex.finditer(texto):
            chave = (m.start(), m.end())
            if chave in vistos:
                continue
            valor = m.group(0).strip()
            ajuste = _ajustar_inicio_de_frase(texto, m.start(), valor)
            if ajuste is None:
                continue
            inicio, valor = ajuste

            # Lugar não é pessoa. Pode (e muitas vezes deve) ser anonimizado,
            # porque identifica, mas não recebe papel processual nem pseudônimo
            # de parte: o requerido em "REQUERIDO: ESTADO DE SANTA CATARINA" é
            # o Estado, e não a localidade.
            deslocamento, aparado = aparar_vocabulario(valor)
            local = localidade_em(texto, inicio, valor, (deslocamento, aparado))
            if local is not None:
                recuo, nome_local = local
                achados.append(
                    Achado(
                        Categoria.LOCALIDADE,
                        nome_local,
                        inicio + recuo,
                        inicio + recuo + len(nome_local),
                        0.72,
                        "localidade",
                        "Cidade, estado ou comarca",
                        requer_revisao=True,
                    )
                )
                vistos.add(chave)
                continue

            if not aparado:
                continue
            valor = aparado
            inicio += deslocamento
            papel, rotulado = papel_do_contexto(texto, inicio)
            avaliacao = avaliar_nome(
                valor,
                rotulado,
                caixa_alta=caixa_alta,
                contexto_medicamento=tem_contexto(texto, inicio, "medicamento", janela=40),
            )
            if not avaliacao.aceito:
                _log.debug("nome descartado (%s)", avaliacao.motivo)
                continue
            achados.append(
                Achado(
                    Categoria.NOME_PESSOA,
                    valor,
                    inicio,
                    inicio + len(valor),
                    avaliacao.confianca,
                    detector,
                    avaliacao.motivo,
                    papel=papel,
                    requer_revisao=not rotulado,
                )
            )
            vistos.add(chave)
            vistos.add((inicio, inicio + len(valor)))

    return achados


# ------------------------------------------------------ NER local (opcional)
_NER_CARREGADO: dict[str, object] = {}


def carregar_ner_local(caminho_modelo: str):
    """Carrega um modelo spaCy a partir de um diretório local, se existir.

    Nunca baixa modelos. Retorna ``None`` quando não houver modelo utilizável.
    """
    if not caminho_modelo:
        return None
    if caminho_modelo in _NER_CARREGADO:
        return _NER_CARREGADO[caminho_modelo]
    try:  # pragma: no cover - depende de instalação local opcional
        import spacy

        nlp = spacy.load(caminho_modelo)
        _NER_CARREGADO[caminho_modelo] = nlp
        _log.info("Modelo de reconhecimento de entidades local carregado.")
        return nlp
    except Exception as exc:  # pragma: no cover
        _log.warning("Modelo NER local indisponível (%s). Prosseguindo com regras.", exc)
        _NER_CARREGADO[caminho_modelo] = None
        return None


def _detectar_ner(texto: str, cfg: Config) -> list[Achado]:
    if not cfg.deteccao.usar_ner_local or not cfg.deteccao.modelo_ner_local:
        return []
    nlp = carregar_ner_local(cfg.deteccao.modelo_ner_local)
    if nlp is None:
        return []
    achados: list[Achado] = []
    try:  # pragma: no cover - caminho exercitado apenas com modelo instalado
        doc = nlp(texto[:1_000_000])
        for ent in doc.ents:
            if ent.label_ not in ("PER", "PERSON", "PESSOA"):
                continue
            if not _nome_valido(ent.text):
                continue
            achados.append(
                Achado(
                    Categoria.NOME_PESSOA,
                    ent.text,
                    ent.start_char,
                    ent.end_char,
                    0.80,
                    "ner_local",
                    "Entidade de pessoa reconhecida por modelo local",
                )
            )
    except Exception as exc:  # pragma: no cover
        _log.warning("Falha no reconhecimento de entidades local: %s", exc)
    return achados


# ----------------------------------------------------- termos personalizados
def _detectar_termos_personalizados(texto: str, cfg: Config) -> list[Achado]:
    achados: list[Achado] = []
    for termo in cfg.deteccao.termos_personalizados:
        termo = (termo or "").strip()
        if len(termo) < 3:
            continue
        for m in re.finditer(re.escape(termo), texto, flags=re.IGNORECASE):
            achados.append(
                Achado(
                    Categoria.OUTRO,
                    m.group(0),
                    m.start(),
                    m.end(),
                    0.99,
                    "termo_personalizado",
                    "Termo incluído manualmente na configuração",
                )
            )
    return achados


# --------------------------------------------------------------- orquestração
def _contem(maior: Achado, menor: Achado) -> bool:
    return maior.inicio <= menor.inicio and maior.fim >= menor.fim


def _remover_sobreposicoes(achados: list[Achado]) -> list[Achado]:
    """Resolve conflitos entre achados que ocupam a mesma região do texto.

    Regras:

    * sobreposição parcial ou intervalo idêntico — prevalece o de maior confiança;
    * contenção (um achado dentro de outro, como o CEP dentro do endereço) — o
      achado externo é mantido e o interno também, desde que sua confiança não
      seja menor. Assim o endereço completo é redigido sem que se perca a
      marcação específica do CEP, e um falso positivo fraco contido em uma
      detecção mais forte é descartado.
    """
    ordenados = sorted(
        achados, key=lambda a: (-a.confianca, -(a.fim - a.inicio), a.inicio)
    )
    aceitos: list[Achado] = []
    for achado in ordenados:
        descartar = False
        for aceito in aceitos:
            sobrepoe = achado.inicio < aceito.fim and achado.fim > aceito.inicio
            if not sobrepoe:
                continue
            if achado.inicio == aceito.inicio and achado.fim == aceito.fim:
                descartar = True
                break
            if _contem(aceito, achado) or _contem(achado, aceito):
                # Contenção: o de menor confiança só sobrevive se for o externo.
                if achado.confianca < aceito.confianca and _contem(aceito, achado):
                    descartar = True
                    break
                continue
            descartar = True  # sobreposição parcial
            break
        if not descartar:
            aceitos.append(achado)
    return sorted(aceitos, key=lambda a: (a.inicio, a.fim))


def detectar(
    texto: str,
    cfg: Config | None = None,
    aplicar_politica_profissionais: bool = True,
) -> list[Achado]:
    """Executa todos os detectores sobre um texto e devolve os achados filtrados."""
    if not texto:
        return []
    config = cfg or Config()
    achados: list[Achado] = []
    achados += _detectar_documentos(texto)
    achados += _detectar_contato(texto)
    achados += _detectar_financeiro(texto)
    achados += _detectar_outros(texto)
    achados += _detectar_localidades(texto)
    achados += _detectar_nomes(texto, config)
    achados += _detectar_ner(texto, config)
    achados += _detectar_termos_personalizados(texto, config)

    ignorados = {_normalizar(t) for t in config.deteccao.termos_ignorados if t}
    filtrados = [
        a
        for a in achados
        # Termos configurados manualmente pelo usuário valem independentemente
        # das categorias ativas: foram indicados de forma explícita.
        if (config.categoria_ativa(a.categoria) or a.detector == "termo_personalizado")
        and _normalizar(a.valor) not in ignorados
    ]
    if aplicar_politica_profissionais and not config.deteccao.anonimizar_profissionais:
        filtrados = [
            a
            for a in filtrados
            if not (a.categoria == Categoria.NOME_PESSOA and a.papel in PAPEIS_PROFISSIONAIS)
        ]
    return _remover_sobreposicoes(filtrados)


def papeis_profissionais_no_texto(texto: str, cfg: Config | None = None) -> set[str]:
    """Nomes que, neste texto, aparecem com papel de profissional.

    Serve para aplicar a política **por pessoa**, e não por ocorrência. O mesmo
    nome costuma aparecer rotulado em um ponto ("RELATOR: JUIZ FEDERAL Fulano")
    e sem rótulo em outro ("assinado por Fulano"). Tratar as duas ocorrências de
    forma diferente redige uma e deixa a outra — o nome continua no documento,
    a redação não serviu para nada e a validação, corretamente, reprova.
    """
    config = cfg or Config()
    encontrados: set[str] = set()
    for achado in _detectar_nomes(texto, config):
        if achado.categoria is Categoria.NOME_PESSOA and achado.papel in PAPEIS_PROFISSIONAIS:
            # Espaços colapsados: o OCR parte o nome na quebra de linha e a
            # comparação com o candidato deixava de casar.
            encontrados.add(re.sub(r"\s+", " ", _normalizar(achado.valor)).strip())
    return encontrados


def _status_inicial(achado: Achado, cfg: Config) -> tuple[Status, bool]:
    """Situação com que a ocorrência entra na revisão.

    Por padrão tudo entra **marcado para remoção**, e o revisor desmarca o que
    deve permanecer (``ConfigDeteccao.confirmar_por_padrao``). A coluna de
    confiança continua indicando o grau de certeza, que é o que orienta o que
    merece um olhar mais atento.
    """
    if cfg.deteccao.confirmar_por_padrao:
        # `requer_revisao` marca a ocorrência como pendência que impede a
        # aprovação. Aqui nada fica pendente: tudo já está decidido (sai), e o
        # revisor decide o contrário desmarcando. O que continua bloqueando a
        # aprovação é o que de fato não foi resolvido — área indeterminada,
        # página não examinada, anexo, assinatura.
        return Status.CONFIRMADO, False
    if achado.confianca >= cfg.deteccao.limiar_auto_confirmacao and not achado.requer_revisao:
        return Status.CONFIRMADO, False
    if achado.confianca < cfg.deteccao.limiar_revisao_obrigatoria:
        return Status.PENDENTE, True
    return Status.DETECTADO, True


def candidatos_de_texto(
    documento: str,
    pagina: int,
    texto: str,
    palavras,
    origem: Origem,
    cfg: Config,
    bboxes_fixas: list[BBox] | None = None,
) -> list[Candidato]:
    """Converte achados de um texto em candidatos com áreas de página resolvidas."""
    candidatos: list[Candidato] = []
    manter_profissional = not cfg.deteccao.anonimizar_profissionais
    for achado in detectar(texto, cfg, aplicar_politica_profissionais=False):
        # O profissional não some da lista: entra desmarcado, com o motivo à
        # vista. Some-lo escondia do revisor que aquele nome ficaria no texto e
        # deixava a validação sem saber que a permanência era intencional.
        profissional = (
            manter_profissional
            and achado.categoria is Categoria.NOME_PESSOA
            and achado.papel in PAPEIS_PROFISSIONAIS
        )
        if bboxes_fixas is not None:
            bboxes = list(bboxes_fixas)
            incerta = False
        else:
            bboxes = bboxes_para_intervalo(palavras, achado.inicio, achado.fim)
            incerta = not bboxes
        status, revisar = _status_inicial(achado, cfg)
        if incerta:
            status, revisar = Status.PENDENTE, True
        if profissional:
            status, revisar = Status.REJEITADO, False
            achado.motivo = (
                "Profissional (advogado, defensor, magistrado, perito ou "
                "servidor); a política vigente não anonimiza profissionais."
            )
        candidatos.append(
            Candidato(
                documento=documento,
                pagina=pagina,
                categoria=achado.categoria,
                valor=achado.valor,
                origem=origem,
                status=status,
                confianca=achado.confianca,
                bboxes=bboxes,
                detector=achado.detector,
                motivo=achado.motivo,
                papel=achado.papel,
                contexto=_contexto_minimizado(texto, achado),
                requer_revisao=revisar,
                bbox_incerta=incerta,
            )
        )
    return candidatos


def _contexto_minimizado(texto: str, achado: Achado, janela: int = 28) -> str:
    """Contexto curto com o próprio valor substituído, para exibição na revisão."""
    ini = max(0, achado.inicio - janela)
    fim = min(len(texto), achado.fim + janela)
    antes = texto[ini : achado.inicio].replace("\n", " ")
    depois = texto[achado.fim : fim].replace("\n", " ")
    return f"...{antes}[{achado.categoria.value}]{depois}..."


def detectar_na_pagina(
    documento: str, pagina: PaginaTexto, cfg: Config
) -> list[Candidato]:
    """Detecta dados pessoais no texto nativo e no OCR de uma página.

    Os dois conjuntos são produzidos separadamente, com origem distinta; a
    deduplicação (mesma ocorrência vista no texto e no OCR) é feita pelo
    gerenciador de candidatos, que registra a origem combinada.
    """
    candidatos: list[Candidato] = []
    if pagina.texto_pdf:
        candidatos += candidatos_de_texto(
            documento,
            pagina.numero,
            pagina.texto_pdf,
            pagina.palavras_pdf,
            Origem.TEXTO,
            cfg,
        )
    if pagina.texto_ocr:
        candidatos += candidatos_de_texto(
            documento,
            pagina.numero,
            pagina.texto_ocr,
            pagina.palavras_ocr,
            Origem.OCR,
            cfg,
        )
    return candidatos
