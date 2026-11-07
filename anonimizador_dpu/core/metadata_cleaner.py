"""Limpeza de metadados e de estruturas internas do PDF.

A limpeza é deliberadamente explícita: cada estrutura removida é registrada, e
cada estrutura que **não** pôde ser tratada é devolvida como pendência, para
que o validador bloqueie a aprovação do documento.
"""

from __future__ import annotations

import fitz

from .audit_logger import obter_logger
from .config import ConfigRedacao

_log = obter_logger("metadados")

#: Chaves de metadados padrão do PDF.
CHAVES_METADADOS = (
    "title",
    "author",
    "subject",
    "keywords",
    "creator",
    "producer",
    "creationDate",
    "modDate",
    "trapped",
    "format",
    "encryption",
)


def limpar_documento(doc: fitz.Document, cfg: ConfigRedacao) -> tuple[list[str], list[str], list[str]]:
    """Limpa metadados e estruturas internas.

    Devolve ``(removidos, estruturas_removidas, nao_tratadas)``.
    """
    removidos: list[str] = []
    estruturas: list[str] = []
    nao_tratadas: list[str] = []

    if cfg.limpar_metadados:
        meta = doc.metadata or {}
        # "format" e "encryption" descrevem o arquivo, não o seu conteúdo.
        presentes = [
            k
            for k in CHAVES_METADADOS
            if meta.get(k) and k not in ("format", "encryption")
        ]
        try:
            doc.set_metadata({})
            removidos.extend(presentes)
        except Exception as exc:
            nao_tratadas.append(f"metadados padrão ({exc})")
        try:
            doc.del_xml_metadata()
            removidos.append("xmp")
        except Exception as exc:
            nao_tratadas.append(f"metadados XMP ({exc})")

    if cfg.remover_marcadores:
        try:
            if doc.get_toc(simple=True):
                doc.set_toc([])
                estruturas.append("marcadores")
        except Exception as exc:
            nao_tratadas.append(f"marcadores ({exc})")

    if cfg.remover_anexos:
        try:
            nomes = list(doc.embfile_names())
            for nome in nomes:
                doc.embfile_del(nome)
            if nomes:
                estruturas.append(f"arquivos incorporados ({len(nomes)})")
        except Exception as exc:
            nao_tratadas.append(f"arquivos incorporados ({exc})")
    else:
        try:
            if doc.embfile_names():
                nao_tratadas.append("arquivos incorporados mantidos por configuração")
        except Exception:  # pragma: no cover
            pass

    anotacoes = 0
    links = 0
    widgets = 0
    for page in doc:
        if cfg.remover_anotacoes:
            try:
                for annot in list(page.annots() or []):
                    page.delete_annot(annot)
                    anotacoes += 1
            except Exception as exc:
                nao_tratadas.append(f"anotações da página {page.number + 1} ({exc})")
        if cfg.remover_links:
            try:
                for link in page.get_links() or []:
                    page.delete_link(link)
                    links += 1
            except Exception as exc:
                nao_tratadas.append(f"links da página {page.number + 1} ({exc})")
        if cfg.remover_formularios:
            try:
                for widget in list(page.widgets() or []):
                    page.delete_widget(widget)
                    widgets += 1
            except Exception as exc:
                nao_tratadas.append(f"campos de formulário da página {page.number + 1} ({exc})")

    if anotacoes:
        estruturas.append(f"anotações ({anotacoes})")
    if links:
        estruturas.append(f"links ({links})")
    if widgets:
        estruturas.append(f"campos de formulário ({widgets})")

    # Camadas de conteúdo opcional não são desmontadas por esta versão.
    try:
        ocgs = doc.get_ocgs() or {}
        if ocgs:
            nao_tratadas.append(
                f"camadas de conteúdo opcional ({len(ocgs)}) — exigem reconstrução da página"
            )
    except Exception:  # pragma: no cover
        pass

    return removidos, estruturas, nao_tratadas


def higienizar(doc: fitz.Document) -> list[str]:
    """Aplica a higienização estrutural do PyMuPDF (``scrub``).

    Remove JavaScript, texto oculto, miniaturas, campos redefiníveis e metadados
    residuais. As anotações de redação **não** são reaplicadas aqui: a redação
    efetiva já ocorreu antes, com remoção de pixels de imagem.
    """
    aplicadas: list[str] = []
    try:
        doc.scrub(
            attached_files=True,
            clean_pages=True,
            embedded_files=True,
            hidden_text=True,
            javascript=True,
            metadata=True,
            redactions=False,
            remove_links=True,
            reset_fields=True,
            reset_responses=True,
            thumbnails=True,
            xml_metadata=True,
        )
        aplicadas.append("scrub: javascript, texto oculto, miniaturas, anexos, metadados")
    except Exception as exc:
        _log.warning("Higienização estrutural parcial: %s", exc)
        aplicadas.append(f"scrub falhou: {exc}")
    return aplicadas


def metadados_residuais(doc: fitz.Document) -> list[str]:
    """Metadados ainda presentes no documento de saída."""
    residuais = [k for k, v in (doc.metadata or {}).items() if v and k not in ("format", "encryption")]
    try:
        if doc.xref_xml_metadata > 0:
            residuais.append("xmp")
    except Exception:  # pragma: no cover
        try:
            if doc.get_xml_metadata():
                residuais.append("xmp")
        except Exception:
            pass
    return residuais
