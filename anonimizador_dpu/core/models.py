"""Modelos de dados do Anonimizador DPU.

Todas as estruturas que circulam entre os módulos (inspeção, extração, detecção,
redação, validação e relatório) são definidas aqui.

Princípio de segurança aplicado neste módulo: o valor original de um dado pessoal
(`Candidato.valor`) existe apenas em memória durante a sessão. As funções de
serialização (`to_dict`) nunca exportam o valor original — exportam apenas uma
forma mascarada e um hash salgado, adequados a auditoria.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

# Sal de sessão: usado para gerar hashes de correlação que não permitem
# reconstruir o valor original nem comparar dados entre execuções diferentes.
_SAL_SESSAO = secrets.token_bytes(16)


def hash_sessao(valor: str) -> str:
    """Hash curto e salgado por sessão, para correlacionar ocorrências sem expor o valor."""
    digest = hashlib.sha256(_SAL_SESSAO + valor.strip().lower().encode("utf-8"))
    return digest.hexdigest()[:16]


def mascarar(valor: str, visiveis: int = 2) -> str:
    """Mascara um valor preservando apenas um prefixo mínimo, para exibição em relatórios."""
    if valor is None:
        return ""
    texto = str(valor)
    if len(texto) <= visiveis:
        return "*" * len(texto)
    return texto[:visiveis] + "*" * min(len(texto) - visiveis, 12)


class Grupo(str, Enum):
    """Grupos de categorias conforme a política de anonimização (itens A a H)."""

    A_IDENTIFICACAO = "A_IDENTIFICACAO"
    B_CONTATO_LOCALIZACAO = "B_CONTATO_LOCALIZACAO"
    C_FINANCEIRO = "C_FINANCEIRO"
    D_PROCESSUAL = "D_PROCESSUAL"
    E_PESSOAS_RELACIONADAS = "E_PESSOAS_RELACIONADAS"
    F_SENSIVEL = "F_SENSIVEL"
    G_ANEXOS = "G_ANEXOS"
    H_OUTROS = "H_OUTROS"


class Categoria(str, Enum):
    """Categorias de dados pessoais passíveis de anonimização."""

    # A — identificação pessoal
    NOME_PESSOA = "NOME_PESSOA"
    CPF = "CPF"
    RG = "RG"
    CNH = "CNH"
    PASSAPORTE = "PASSAPORTE"
    TITULO_ELEITOR = "TITULO_ELEITOR"
    NIT_PIS_PASEP = "NIT_PIS_PASEP"
    DATA_NASCIMENTO = "DATA_NASCIMENTO"
    ASSINATURA = "ASSINATURA"

    # B — contato e localização
    ENDERECO = "ENDERECO"
    LOCALIDADE = "LOCALIDADE"
    CEP = "CEP"
    TELEFONE = "TELEFONE"
    EMAIL = "EMAIL"

    # C — dados financeiros
    CONTA_BANCARIA = "CONTA_BANCARIA"
    AGENCIA_BANCARIA = "AGENCIA_BANCARIA"
    CHAVE_PIX = "CHAVE_PIX"
    CARTAO = "CARTAO"

    # D — identificadores processuais e administrativos
    PROCESSO_CNJ = "PROCESSO_CNJ"
    PROTOCOLO = "PROTOCOLO"
    BENEFICIO_NB = "BENEFICIO_NB"
    MATRICULA = "MATRICULA"

    # C/D — pessoa jurídica (tratada à parte: nem sempre é dado pessoal)
    CNPJ = "CNPJ"

    # F — dados sensíveis
    DADO_SAUDE = "DADO_SAUDE"

    # H — outros identificadores
    PLACA_VEICULO = "PLACA_VEICULO"
    URL_COM_TOKEN = "URL_COM_TOKEN"

    # Uso interno
    REGIAO_MANUAL = "REGIAO_MANUAL"
    OUTRO = "OUTRO"


#: Metadados de cada categoria: (rótulo em PT-BR, grupo, ativa por padrão)
CATEGORIAS_INFO: dict[Categoria, tuple[str, Grupo, bool]] = {
    Categoria.NOME_PESSOA: ("Nome de pessoa", Grupo.A_IDENTIFICACAO, True),
    Categoria.CPF: ("CPF", Grupo.A_IDENTIFICACAO, True),
    Categoria.RG: ("RG / documento de identidade", Grupo.A_IDENTIFICACAO, True),
    Categoria.CNH: ("CNH", Grupo.A_IDENTIFICACAO, True),
    Categoria.PASSAPORTE: ("Passaporte", Grupo.A_IDENTIFICACAO, True),
    Categoria.TITULO_ELEITOR: ("Título de eleitor", Grupo.A_IDENTIFICACAO, True),
    Categoria.NIT_PIS_PASEP: ("NIT / PIS / PASEP", Grupo.A_IDENTIFICACAO, True),
    Categoria.DATA_NASCIMENTO: ("Data de nascimento", Grupo.A_IDENTIFICACAO, True),
    Categoria.ASSINATURA: ("Assinatura (imagem)", Grupo.A_IDENTIFICACAO, True),
    Categoria.ENDERECO: ("Endereço", Grupo.B_CONTATO_LOCALIZACAO, True),
    Categoria.LOCALIDADE: (
        "Cidade / estado / comarca",
        Grupo.B_CONTATO_LOCALIZACAO,
        True,
    ),
    Categoria.CEP: ("CEP", Grupo.B_CONTATO_LOCALIZACAO, True),
    Categoria.TELEFONE: ("Telefone / celular", Grupo.B_CONTATO_LOCALIZACAO, True),
    Categoria.EMAIL: ("E-mail", Grupo.B_CONTATO_LOCALIZACAO, True),
    Categoria.CONTA_BANCARIA: ("Conta bancária", Grupo.C_FINANCEIRO, True),
    Categoria.AGENCIA_BANCARIA: ("Agência bancária", Grupo.C_FINANCEIRO, True),
    Categoria.CHAVE_PIX: ("Chave Pix", Grupo.C_FINANCEIRO, True),
    Categoria.CARTAO: ("Cartão", Grupo.C_FINANCEIRO, True),
    Categoria.PROCESSO_CNJ: ("Número de processo (CNJ)", Grupo.D_PROCESSUAL, True),
    Categoria.PROTOCOLO: ("Protocolo / requerimento", Grupo.D_PROCESSUAL, False),
    Categoria.BENEFICIO_NB: ("Benefício (NB)", Grupo.D_PROCESSUAL, True),
    Categoria.MATRICULA: ("Matrícula / registro pessoal", Grupo.D_PROCESSUAL, False),
    Categoria.CNPJ: ("CNPJ", Grupo.C_FINANCEIRO, False),
    Categoria.DADO_SAUDE: ("Dado de saúde (CID e afins)", Grupo.F_SENSIVEL, True),
    Categoria.PLACA_VEICULO: ("Placa de veículo", Grupo.H_OUTROS, True),
    Categoria.URL_COM_TOKEN: ("URL com token pessoal", Grupo.H_OUTROS, True),
    Categoria.REGIAO_MANUAL: ("Região marcada manualmente", Grupo.H_OUTROS, True),
    Categoria.OUTRO: ("Outro", Grupo.H_OUTROS, False),
}


def rotulo_categoria(categoria: Categoria) -> str:
    return CATEGORIAS_INFO.get(categoria, (categoria.value, Grupo.H_OUTROS, False))[0]


class Papel(str, Enum):
    """Papel processual atribuído a uma pessoa, usado na geração de pseudônimos."""

    ASSISTIDO = "ASSISTIDO"
    REQUERENTE = "REQUERENTE"
    REQUERIDO = "REQUERIDO"
    TESTEMUNHA = "TESTEMUNHA"
    ADVOGADO = "ADVOGADO"
    DEFENSOR = "DEFENSOR"
    MAGISTRADO = "MAGISTRADO"
    PERITO = "PERITO"
    SERVIDOR = "SERVIDOR"
    FAMILIAR = "FAMILIAR"
    CRIANCA_ADOLESCENTE = "CRIANCA_ADOLESCENTE"
    TERCEIRO = "TERCEIRO"


class Origem(str, Enum):
    """Fonte da ocorrência detectada."""

    TEXTO = "TEXTO"
    OCR = "OCR"
    TEXTO_E_OCR = "TEXTO_E_OCR"
    METADADO = "METADADO"
    ANOTACAO = "ANOTACAO"
    FORMULARIO = "FORMULARIO"
    ANEXO = "ANEXO"
    MANUAL = "MANUAL"


class Status(str, Enum):
    """Ciclo de vida de um candidato à anonimização."""

    DETECTADO = "DETECTADO"
    CONFIRMADO = "CONFIRMADO"
    REJEITADO = "REJEITADO"
    PENDENTE = "PENDENTE"
    REDIGIDO = "REDIGIDO"
    VERIFICADO = "VERIFICADO"
    FALHA_CRITICA = "FALHA_CRITICA"


ROTULOS_STATUS: dict[Status, str] = {
    Status.DETECTADO: "Detectado",
    Status.CONFIRMADO: "Confirmado para redação",
    Status.REJEITADO: "Rejeitado (falso positivo)",
    Status.PENDENTE: "Pendente de decisão",
    Status.REDIGIDO: "Redigido",
    Status.VERIFICADO: "Verificado",
    Status.FALHA_CRITICA: "Falha crítica",
}


class Severidade(str, Enum):
    INFO = "INFO"
    AVISO = "AVISO"
    CRITICO = "CRITICO"


class Veredito(str, Enum):
    """Classificação final do documento de saída."""

    APROVADO_TESTES = "APROVADO_NOS_TESTES_AUTOMATIZADOS"
    APROVADO_COM_RESSALVAS = "APROVADO_COM_RESSALVAS"
    REVISAO_OBRIGATORIA = "REVISAO_OBRIGATORIA"
    REPROVADO = "REPROVADO"


ROTULOS_VEREDITO: dict[Veredito, str] = {
    Veredito.APROVADO_TESTES: "APROVADO NOS TESTES AUTOMATIZADOS",
    Veredito.APROVADO_COM_RESSALVAS: "APROVADO COM RESSALVAS",
    Veredito.REVISAO_OBRIGATORIA: "REVISÃO OBRIGATÓRIA",
    Veredito.REPROVADO: "REPROVADO",
}


class TipoPagina(str, Enum):
    TEXTO = "TEXTO"
    DIGITALIZADA = "DIGITALIZADA"
    HIBRIDA = "HIBRIDA"
    VAZIA = "VAZIA"
    NAO_EXAMINADA = "NAO_EXAMINADA"


BBox = tuple[float, float, float, float]


@dataclass
class Risco:
    """Risco estrutural ou operacional identificado em um documento."""

    codigo: str
    descricao: str
    severidade: Severidade = Severidade.AVISO
    pagina: int | None = None
    bloqueia_aprovacao: bool = False
    detalhe: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "codigo": self.codigo,
            "descricao": self.descricao,
            "severidade": self.severidade.value,
            "pagina": (self.pagina + 1) if self.pagina is not None else None,
            "bloqueia_aprovacao": self.bloqueia_aprovacao,
            "detalhe": self.detalhe,
        }


@dataclass
class PaginaInfo:
    """Resultado da inspeção estrutural de uma página."""

    numero: int  # 0-based
    tipo: TipoPagina = TipoPagina.NAO_EXAMINADA
    caracteres_texto: int = 0
    qtd_imagens: int = 0
    area_imagens_pct: float = 0.0
    qtd_anotacoes: int = 0
    qtd_links: int = 0
    qtd_campos_formulario: int = 0
    tem_vetores: bool = False
    rotacao: int = 0
    largura: float = 0.0
    altura: float = 0.0
    erro: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pagina": self.numero + 1,
            "tipo": self.tipo.value,
            "caracteres_texto": self.caracteres_texto,
            "qtd_imagens": self.qtd_imagens,
            "area_imagens_pct": round(self.area_imagens_pct, 2),
            "qtd_anotacoes": self.qtd_anotacoes,
            "qtd_links": self.qtd_links,
            "qtd_campos_formulario": self.qtd_campos_formulario,
            "tem_vetores": self.tem_vetores,
            "rotacao": self.rotacao,
            "erro": self.erro,
        }


@dataclass
class Inspecao:
    """Relatório estrutural completo de um PDF de entrada."""

    arquivo: str
    paginas: list[PaginaInfo] = field(default_factory=list)
    total_paginas: int = 0
    metadados: dict[str, str] = field(default_factory=dict)
    tem_xmp: bool = False
    tem_formulario: bool = False
    qtd_anotacoes: int = 0
    qtd_links: int = 0
    arquivos_incorporados: list[str] = field(default_factory=list)
    eh_portfolio: bool = False
    camadas_ocg: list[str] = field(default_factory=list)
    assinaturas: list[str] = field(default_factory=list)
    marcadores: int = 0
    criptografado: bool = False
    permissoes: int = 0
    riscos: list[Risco] = field(default_factory=list)
    tamanho_bytes: int = 0
    sha256_entrada: str = ""
    erro_fatal: str | None = None

    @property
    def paginas_texto(self) -> int:
        return sum(1 for p in self.paginas if p.tipo == TipoPagina.TEXTO)

    @property
    def paginas_digitalizadas(self) -> int:
        return sum(1 for p in self.paginas if p.tipo == TipoPagina.DIGITALIZADA)

    @property
    def paginas_hibridas(self) -> int:
        return sum(1 for p in self.paginas if p.tipo == TipoPagina.HIBRIDA)

    @property
    def paginas_vazias(self) -> int:
        return sum(1 for p in self.paginas if p.tipo == TipoPagina.VAZIA)

    def riscos_bloqueantes(self) -> list[Risco]:
        return [r for r in self.riscos if r.bloqueia_aprovacao]

    def to_dict(self) -> dict[str, Any]:
        return {
            "arquivo": self.arquivo,
            "total_paginas": self.total_paginas,
            "paginas_com_texto": self.paginas_texto,
            "paginas_digitalizadas": self.paginas_digitalizadas,
            "paginas_hibridas": self.paginas_hibridas,
            "paginas_vazias": self.paginas_vazias,
            "chaves_metadados": sorted(self.metadados.keys()),
            "tem_xmp": self.tem_xmp,
            "tem_formulario": self.tem_formulario,
            "qtd_anotacoes": self.qtd_anotacoes,
            "qtd_links": self.qtd_links,
            "qtd_arquivos_incorporados": len(self.arquivos_incorporados),
            "eh_portfolio": self.eh_portfolio,
            "camadas_ocg": self.camadas_ocg,
            "qtd_assinaturas": len(self.assinaturas),
            "marcadores": self.marcadores,
            "criptografado": self.criptografado,
            "tamanho_bytes": self.tamanho_bytes,
            "sha256_entrada": self.sha256_entrada,
            "riscos": [r.to_dict() for r in self.riscos],
            "erro_fatal": self.erro_fatal,
            "paginas": [p.to_dict() for p in self.paginas],
        }


@dataclass
class PalavraPos:
    """Uma palavra com sua posição na página e seu intervalo no texto linearizado.

    `bbox` está sempre em coordenadas de página do PDF (pontos), mesmo quando a
    palavra vem do OCR de uma imagem renderizada.
    """

    texto: str
    bbox: BBox
    inicio: int = -1
    fim: int = -1
    confianca: float = 100.0


@dataclass
class PaginaTexto:
    """Texto de uma página, com proveniência e mapa de posições."""

    numero: int
    texto_pdf: str = ""
    palavras_pdf: list[PalavraPos] = field(default_factory=list)
    texto_ocr: str = ""
    palavras_ocr: list[PalavraPos] = field(default_factory=list)
    ocr_executado: bool = False
    ocr_confianca_media: float = 0.0
    ocr_cobertura: float = 0.0
    ocr_falhou: bool = False
    ocr_erro: str = ""
    examinada: bool = False
    observacao: str = ""

    @property
    def texto_combinado(self) -> str:
        if self.texto_ocr and self.texto_pdf:
            return self.texto_pdf + "\n" + self.texto_ocr
        return self.texto_pdf or self.texto_ocr


@dataclass
class Candidato:
    """Uma ocorrência de dado pessoal candidata à redação.

    `valor` é o texto original e permanece apenas em memória.
    """

    documento: str
    pagina: int
    categoria: Categoria
    valor: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    origem: Origem = Origem.TEXTO
    status: Status = Status.DETECTADO
    confianca: float = 0.5
    bboxes: list[BBox] = field(default_factory=list)
    detector: str = ""
    motivo: str = ""
    papel: Papel | None = None
    pseudonimo: str | None = None
    entidade_id: str | None = None
    contexto: str = ""
    requer_revisao: bool = False
    falha: str | None = None
    bbox_incerta: bool = False
    ocorrencias_texto: int = 1

    @property
    def chave(self) -> str:
        """Chave de correlação da mesma ocorrência textual na mesma categoria."""
        return f"{self.categoria.value}:{self.valor.strip().lower()}"

    @property
    def hash_valor(self) -> str:
        return hash_sessao(self.valor)

    def valor_mascarado(self) -> str:
        return mascarar(self.valor)

    def to_dict(self) -> dict[str, Any]:
        """Serialização segura: nunca inclui o valor original."""
        return {
            "id": self.id,
            "documento": self.documento,
            "pagina": self.pagina + 1,
            "categoria": self.categoria.value,
            "categoria_rotulo": rotulo_categoria(self.categoria),
            "origem": self.origem.value,
            "status": self.status.value,
            "confianca": round(self.confianca, 3),
            "detector": self.detector,
            "motivo": self.motivo,
            "papel": self.papel.value if self.papel else None,
            "pseudonimo": self.pseudonimo,
            "valor_mascarado": self.valor_mascarado(),
            "hash_valor_sessao": self.hash_valor,
            "qtd_areas": len(self.bboxes),
            "bbox_incerta": self.bbox_incerta,
            "requer_revisao": self.requer_revisao,
            "falha": self.falha,
        }


@dataclass
class ResultadoRedacao:
    """Resultado da aplicação da redação em um documento."""

    arquivo_saida: str = ""
    redacoes_aplicadas: int = 0
    redacoes_texto: int = 0
    redacoes_imagem: int = 0
    paginas_rasterizadas: list[int] = field(default_factory=list)
    falhas: list[Risco] = field(default_factory=list)
    metadados_removidos: list[str] = field(default_factory=list)
    estruturas_removidas: list[str] = field(default_factory=list)
    estruturas_nao_tratadas: list[str] = field(default_factory=list)
    sha256_saida: str = ""
    cancelado: bool = False


@dataclass
class ResultadoValidacao:
    """Resultado da validação independente do PDF de saída."""

    veredito: Veredito = Veredito.REVISAO_OBRIGATORIA
    residuais: list[Candidato] = field(default_factory=list)
    residuais_conhecidos: int = 0
    riscos: list[Risco] = field(default_factory=list)
    paginas_verificadas_texto: int = 0
    paginas_verificadas_ocr: int = 0
    paginas_sem_cobertura: list[int] = field(default_factory=list)
    areas_redacao_conferidas: int = 0
    areas_redacao_falhas: list[int] = field(default_factory=list)
    metadados_residuais: list[str] = field(default_factory=list)
    anexos_residuais: list[str] = field(default_factory=list)
    abriu_corretamente: bool = False
    observacoes: list[str] = field(default_factory=list)

    @property
    def aprovado(self) -> bool:
        return self.veredito == Veredito.APROVADO_TESTES


@dataclass
class RelatorioDocumento:
    """Relatório técnico por documento processado."""

    arquivo_entrada: str
    arquivo_saida: str = ""
    inicio: datetime = field(default_factory=datetime.now)
    fim: datetime | None = None
    versao_app: str = ""
    inspecao: Inspecao | None = None
    candidatos: list[Candidato] = field(default_factory=list)
    redacao: ResultadoRedacao | None = None
    validacao: ResultadoValidacao | None = None
    paginas_por_texto: int = 0
    paginas_por_ocr: int = 0
    paginas_nao_examinadas: list[int] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    erro: str | None = None
    cancelado: bool = False

    @property
    def veredito(self) -> Veredito:
        if self.erro:
            return Veredito.REPROVADO
        if self.validacao is None:
            return Veredito.REVISAO_OBRIGATORIA
        return self.validacao.veredito
