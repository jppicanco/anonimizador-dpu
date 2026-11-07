"""Configuração da aplicação e política de anonimização.

A configuração é gravada em arquivo JSON local (nunca remoto). Nenhum valor
aqui habilita acesso a rede: o aplicativo opera integralmente offline.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .models import CATEGORIAS_INFO, Categoria

APP_NOME = "Anonimizador DPU"
APP_VERSAO = "0.1.0"
APP_ID = "anonimizador_dpu"

#: Avisos exibidos na interface e nos relatórios. Não são opcionais.
AVISO_PRINCIPAL = (
    "A aprovação técnica automatizada NÃO garante anonimização integral e NÃO "
    "substitui a revisão humana nem a avaliação de conformidade com a "
    "regulamentação da DPU."
)
AVISO_SSD = (
    "A exclusão de arquivos temporários não garante eliminação física "
    "irrecuperável em discos SSD."
)
AVISO_ASSINATURA = (
    "Documentos assinados digitalmente perdem a validade da assinatura quando "
    "modificados. O aplicativo não preserva assinaturas digitais."
)


def diretorio_config() -> Path:
    """Diretório local de configuração do usuário (sem acesso a rede)."""
    base = os.environ.get("APPDATA") or os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / APP_ID
    return Path.home() / f".{APP_ID}"


def caminho_config() -> Path:
    return diretorio_config() / "config.json"


def _raiz_da_aplicacao() -> Path:
    """Pasta onde o aplicativo está instalado.

    No executável empacotado, é a pasta do próprio ``.exe``; a partir do
    código-fonte, é a raiz do projeto.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent.parent


def _tesseract_padrao() -> str:
    """Localiza o executável do Tesseract sem baixar nada.

    A busca começa **ao lado do aplicativo**, porque o pacote distribuído traz
    o Tesseract embutido: assim o colega descompacta e usa, sem instalar nada
    nem ter privilégio de administrador. Em seguida vem o PATH e, por fim, os
    locais usuais de instalação.
    """
    embutido = _raiz_da_aplicacao() / "tesseract" / "tesseract.exe"
    if embutido.exists():
        return str(embutido)

    achado = shutil.which("tesseract")
    if achado:
        return achado
    candidatos = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        "/usr/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for c in candidatos:
        if Path(c).exists():
            return c
    return ""


@dataclass
class ConfigOCR:
    habilitado: bool = True
    idiomas: str = "por"
    dpi: int = 300
    psm: int = 3
    caminho_tesseract: str = field(default_factory=_tesseract_padrao)
    tessdata: str = ""
    confianca_minima_palavra: float = 40.0
    #: Proporção mínima de palavras com confiança aceitável para considerar a
    #: página efetivamente examinada por OCR.
    cobertura_minima: float = 0.60
    timeout_pagina_s: int = 120


@dataclass
class ConfigLimites:
    max_paginas: int = 3000
    max_mb_arquivo: int = 500
    max_mb_imagem_pagina: int = 80
    timeout_documento_s: int = 7200
    max_dimensao_render_px: int = 10000


@dataclass
class ConfigRedacao:
    #: "tarja" remove o conteúdo e deixa área preenchida; "pseudonimo" remove e
    #: escreve o rótulo substituto por cima (preserva legibilidade jurídica).
    modo: str = "pseudonimo"
    cor_tarja: tuple[float, float, float] = (0.0, 0.0, 0.0)
    cor_texto: tuple[float, float, float] = (1.0, 1.0, 1.0)
    tamanho_fonte_min: float = 5.0
    #: Margem (pontos) acrescida à área de redação em páginas digitalizadas.
    margem_ocr_pt: float = 1.5
    #: Rasteriza a página inteira quando a estrutura não puder ser limpa com segurança.
    permitir_rasterizacao: bool = True
    dpi_rasterizacao: int = 200
    remover_anotacoes: bool = True
    remover_formularios: bool = True
    remover_links: bool = True
    remover_anexos: bool = True
    remover_marcadores: bool = True
    limpar_metadados: bool = True


@dataclass
class ConfigDeteccao:
    #: Confiança mínima para confirmação automática em lote.
    limiar_auto_confirmacao: float = 0.90
    #: Abaixo deste limiar a ocorrência é marcada como PENDENTE (exige decisão humana).
    limiar_revisao_obrigatoria: float = 0.70
    #: Toda ocorrência detectada já entra marcada para remoção, e o revisor
    #: **desmarca** o que não deve sair. O padrão falha para o lado seguro:
    #: esquecer de desmarcar remove algo a mais, enquanto esquecer de confirmar
    #: deixaria dado pessoal no documento.
    #:
    #: Com `False`, volta o comportamento anterior: cada ocorrência precisa ser
    #: confirmada, e só as de alta confiança entram confirmadas sozinhas.
    confirmar_por_padrao: bool = True
    anonimizar_profissionais: bool = False  # advogados, magistrados, servidores, peritos
    anonimizar_orgaos: bool = False
    detectar_nomes_heuristica: bool = True
    usar_ner_local: bool = True  # só é usado se um modelo local estiver instalado
    modelo_ner_local: str = ""  # caminho local; vazio = não usar
    termos_personalizados: list[str] = field(default_factory=list)
    termos_ignorados: list[str] = field(default_factory=list)


@dataclass
class Config:
    categorias_ativas: list[str] = field(
        default_factory=lambda: [
            c.value for c, (_, _, padrao) in CATEGORIAS_INFO.items() if padrao
        ]
    )
    ocr: ConfigOCR = field(default_factory=ConfigOCR)
    limites: ConfigLimites = field(default_factory=ConfigLimites)
    redacao: ConfigRedacao = field(default_factory=ConfigRedacao)
    deteccao: ConfigDeteccao = field(default_factory=ConfigDeteccao)
    pasta_saida_padrao: str = ""
    sufixo_saida: str = "_ANONIMIZADO"
    #: Por padrão NÃO é gerada tabela de reversão (pseudônimo -> valor original).
    permitir_tabela_reversao: bool = False
    #: Política institucional que admite "APROVADO COM RESSALVAS".
    permitir_aprovacao_com_ressalvas: bool = False
    nivel_log: str = "INFO"

    # ------------------------------------------------------------------ util
    def categoria_ativa(self, categoria: Categoria) -> bool:
        return categoria.value in self.categorias_ativas

    def ativar(self, categoria: Categoria, ativa: bool) -> None:
        if ativa and categoria.value not in self.categorias_ativas:
            self.categorias_ativas.append(categoria.value)
        elif not ativa and categoria.value in self.categorias_ativas:
            self.categorias_ativas.remove(categoria.value)

    # ------------------------------------------------------- persistência
    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, dados: dict) -> "Config":
        cfg = cls()
        for campo, valor in dados.items():
            if not hasattr(cfg, campo):
                continue
            atual = getattr(cfg, campo)
            if isinstance(atual, (ConfigOCR, ConfigLimites, ConfigRedacao, ConfigDeteccao)):
                if isinstance(valor, dict):
                    for k, v in valor.items():
                        if hasattr(atual, k):
                            setattr(atual, k, v)
            else:
                setattr(cfg, campo, valor)
        return cfg

    def salvar(self, caminho: Path | None = None) -> Path:
        destino = Path(caminho) if caminho else caminho_config()
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        try:
            os.chmod(destino, 0o600)
        except OSError:
            pass
        return destino

    @classmethod
    def carregar(cls, caminho: Path | None = None) -> "Config":
        origem = Path(caminho) if caminho else caminho_config()
        if not origem.exists():
            return cls()
        try:
            return cls.from_dict(json.loads(origem.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return cls()


def info_ambiente() -> dict[str, str]:
    """Informações de ambiente para o relatório (sem dados pessoais)."""
    import platform

    return {
        "aplicativo": APP_NOME,
        "versao": APP_VERSAO,
        "python": sys.version.split()[0],
        "sistema": f"{platform.system()} {platform.release()}",
    }
