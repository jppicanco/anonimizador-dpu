"""Inspeção estrutural do PDF de entrada.

A inspeção ocorre antes de qualquer anonimização e produz:
  * a classificação de cada página (texto, digitalizada, híbrida, vazia);
  * o inventário de estruturas internas (formulários, anotações, links,
    arquivos incorporados, camadas, assinaturas, metadados);
  * uma lista de riscos estruturais, com indicação explícita do que bloqueia a
    aprovação do documento.

Regra adotada: o sucesso da extração de texto NÃO basta para considerar um PDF
simples. Estruturas não tratáveis com segurança nunca são ignoradas em silêncio.
"""

from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF

from .audit_logger import obter_logger
from .config import Config
from .models import Inspecao, PaginaInfo, Risco, Severidade, TipoPagina
from .security import sha256_arquivo, validar_pdf_entrada

_log = obter_logger("inspector")

#: Abaixo deste número de caracteres a página não é considerada "com texto".
MIN_CARACTERES_TEXTO = 24
#: Acima desta fração da área da página coberta por imagens, há conteúdo visual relevante.
MIN_AREA_IMAGEM = 0.12


def _area_imagens(page: fitz.Page) -> tuple[int, float]:
    """Retorna (quantidade de imagens, fração da área da página coberta)."""
    try:
        infos = page.get_image_info()
    except Exception:  # pragma: no cover - PDFs malformados
        return 0, 0.0
    area_pagina = abs(page.rect.get_area()) or 1.0
    coberta = 0.0
    for info in infos:
        bbox = fitz.Rect(info.get("bbox", (0, 0, 0, 0)))
        inter = bbox & page.rect
        if not inter.is_empty:
            coberta += abs(inter.get_area())
    return len(infos), min(coberta / area_pagina, 1.0)


def _classificar(caracteres: int, qtd_imagens: int, area_img: float) -> TipoPagina:
    tem_texto = caracteres >= MIN_CARACTERES_TEXTO
    tem_imagem = qtd_imagens > 0 and area_img >= MIN_AREA_IMAGEM
    if tem_texto and tem_imagem:
        return TipoPagina.HIBRIDA
    if tem_texto:
        return TipoPagina.TEXTO
    if qtd_imagens > 0:
        return TipoPagina.DIGITALIZADA
    return TipoPagina.VAZIA


def _detectar_portfolio(doc: fitz.Document) -> bool:
    try:
        valor = doc.xref_get_key(-1, "Collection")
    except Exception:  # pragma: no cover
        return False
    return bool(valor) and valor[0] not in ("null", "unknown")


def _assinaturas(doc: fitz.Document) -> list[str]:
    encontradas: list[str] = []
    try:
        flags = doc.get_sigflags()
    except Exception:  # pragma: no cover
        flags = -1
    if flags and flags > 0:
        encontradas.append(f"SigFlags={flags}")
    for pagina in doc:
        try:
            for widget in pagina.widgets() or []:
                if widget.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    encontradas.append(
                        f"Campo de assinatura na página {pagina.number + 1}"
                    )
        except Exception:  # pragma: no cover
            continue
    return encontradas


def inspecionar(caminho: str | Path, config: Config | None = None) -> Inspecao:
    """Inspeciona um PDF e devolve o relatório estrutural completo."""
    cfg = config or Config()
    try:
        entrada = validar_pdf_entrada(caminho, cfg.limites.max_mb_arquivo)
    except Exception as exc:
        insp = Inspecao(arquivo=str(caminho))
        insp.erro_fatal = str(exc)
        insp.riscos.append(
            Risco(
                "ENTRADA_INVALIDA",
                f"Arquivo recusado na validação de entrada: {exc}",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
        return insp

    insp = Inspecao(arquivo=entrada.name, tamanho_bytes=entrada.stat().st_size)
    insp.sha256_entrada = sha256_arquivo(entrada)

    try:
        doc = fitz.open(entrada)
    except Exception as exc:
        insp.erro_fatal = f"Não foi possível abrir o PDF: {exc}"
        insp.riscos.append(
            Risco(
                "PDF_ILEGIVEL",
                "O arquivo não pôde ser aberto como PDF (possivelmente malformado).",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
                detalhe=str(exc)[:200],
            )
        )
        return insp

    with doc:
        if doc.is_encrypted:
            insp.criptografado = True
            if not doc.authenticate(""):
                insp.erro_fatal = "PDF protegido por senha."
                insp.riscos.append(
                    Risco(
                        "PDF_CRIPTOGRAFADO",
                        "PDF protegido por senha; o conteúdo não pode ser examinado.",
                        Severidade.CRITICO,
                        bloqueia_aprovacao=True,
                    )
                )
                return insp
            insp.riscos.append(
                Risco(
                    "PDF_CRIPTOGRAFADO_SEM_SENHA",
                    "PDF possui criptografia com senha vazia; a saída será gerada sem criptografia.",
                    Severidade.AVISO,
                )
            )

        if getattr(doc, "is_repaired", False):
            insp.riscos.append(
                Risco(
                    "PDF_REPARADO",
                    "O PDF apresentava estrutura inconsistente e foi reparado na leitura. "
                    "Objetos podem não ter sido interpretados integralmente.",
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                )
            )

        insp.total_paginas = doc.page_count
        if doc.page_count > cfg.limites.max_paginas:
            insp.riscos.append(
                Risco(
                    "EXCESSO_PAGINAS",
                    f"Documento com {doc.page_count} páginas excede o limite "
                    f"configurado ({cfg.limites.max_paginas}).",
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                )
            )

        insp.metadados = {k: v for k, v in (doc.metadata or {}).items() if v}
        try:
            xmp = doc.xref_xml_metadata
            insp.tem_xmp = bool(xmp) and xmp > 0
        except Exception:
            try:
                insp.tem_xmp = bool(doc.get_xml_metadata())
            except Exception:  # pragma: no cover
                insp.tem_xmp = False

        insp.tem_formulario = bool(doc.is_form_pdf)
        try:
            insp.marcadores = len(doc.get_toc(simple=True) or [])
        except Exception:  # pragma: no cover
            insp.marcadores = 0

        try:
            insp.arquivos_incorporados = list(doc.embfile_names())
        except Exception:  # pragma: no cover
            insp.arquivos_incorporados = []

        try:
            ocgs = doc.get_ocgs() or {}
            insp.camadas_ocg = [str(v.get("name", x)) for x, v in ocgs.items()]
        except Exception:  # pragma: no cover
            insp.camadas_ocg = []

        insp.eh_portfolio = _detectar_portfolio(doc)
        insp.assinaturas = _assinaturas(doc)

        total_anotacoes = 0
        total_links = 0
        for page in doc:
            pinfo = PaginaInfo(
                numero=page.number,
                largura=page.rect.width,
                altura=page.rect.height,
                rotacao=page.rotation,
            )
            try:
                texto = page.get_text("text") or ""
                pinfo.caracteres_texto = len(texto.strip())
                qtd_img, area = _area_imagens(page)
                pinfo.qtd_imagens = qtd_img
                pinfo.area_imagens_pct = area * 100.0
                try:
                    pinfo.qtd_anotacoes = len(list(page.annots() or []))
                except Exception:
                    pinfo.qtd_anotacoes = 0
                pinfo.qtd_links = len(page.get_links() or [])
                try:
                    pinfo.qtd_campos_formulario = len(list(page.widgets() or []))
                except Exception:
                    pinfo.qtd_campos_formulario = 0
                try:
                    pinfo.tem_vetores = bool(page.get_drawings())
                except Exception:
                    pinfo.tem_vetores = False
                pinfo.tipo = _classificar(pinfo.caracteres_texto, qtd_img, area)
            except Exception as exc:  # pragma: no cover - página corrompida
                pinfo.erro = str(exc)[:200]
                pinfo.tipo = TipoPagina.NAO_EXAMINADA
                insp.riscos.append(
                    Risco(
                        "PAGINA_ILEGIVEL",
                        "Página não pôde ser inspecionada.",
                        Severidade.CRITICO,
                        pagina=page.number,
                        bloqueia_aprovacao=True,
                        detalhe=str(exc)[:200],
                    )
                )
            total_anotacoes += pinfo.qtd_anotacoes
            total_links += pinfo.qtd_links
            insp.paginas.append(pinfo)

        insp.qtd_anotacoes = total_anotacoes
        insp.qtd_links = total_links

    _acrescentar_riscos_estruturais(insp)
    _log.info(
        "Inspeção concluída: %d páginas (texto=%d, digitalizadas=%d, híbridas=%d, vazias=%d), %d riscos.",
        insp.total_paginas,
        insp.paginas_texto,
        insp.paginas_digitalizadas,
        insp.paginas_hibridas,
        insp.paginas_vazias,
        len(insp.riscos),
    )
    return insp


def _acrescentar_riscos_estruturais(insp: Inspecao) -> None:
    """Converte o inventário estrutural em riscos, com bloqueios explícitos."""
    if insp.arquivos_incorporados:
        insp.riscos.append(
            Risco(
                "ARQUIVOS_INCORPORADOS",
                f"O PDF contém {len(insp.arquivos_incorporados)} arquivo(s) incorporado(s). "
                "Eles não são abertos nem executados; devem ser removidos ou examinados "
                "separadamente antes de o documento ser considerado tratado.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
    if insp.eh_portfolio:
        insp.riscos.append(
            Risco(
                "PORTFOLIO_PDF",
                "O arquivo é um portfólio PDF (coleção de documentos). O conteúdo dos "
                "documentos internos não é processado por esta versão.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
    if insp.assinaturas:
        insp.riscos.append(
            Risco(
                "ASSINATURA_DIGITAL",
                "O documento contém assinatura digital. Qualquer alteração invalida a "
                "assinatura; o aplicativo não preserva sua validade.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
                detalhe="; ".join(insp.assinaturas[:5]),
            )
        )
    if insp.tem_formulario:
        insp.riscos.append(
            Risco(
                "FORMULARIO_INTERATIVO",
                "O PDF contém formulário interativo. Os valores dos campos podem conter "
                "dados pessoais e serão achatados/removidos conforme a configuração.",
                Severidade.AVISO,
            )
        )
    if insp.qtd_anotacoes:
        insp.riscos.append(
            Risco(
                "ANOTACOES",
                f"O PDF contém {insp.qtd_anotacoes} anotação(ões). O conteúdo de "
                "anotações é examinado e removido conforme a configuração.",
                Severidade.AVISO,
            )
        )
    if insp.camadas_ocg:
        insp.riscos.append(
            Risco(
                "CAMADAS_OCG",
                f"O PDF possui {len(insp.camadas_ocg)} camada(s) de conteúdo opcional. "
                "Conteúdo oculto em camadas pode não ser visível na conferência visual.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
    if insp.qtd_links:
        insp.riscos.append(
            Risco(
                "LINKS",
                f"O PDF contém {insp.qtd_links} link(s). URLs podem conter identificadores pessoais.",
                Severidade.AVISO,
            )
        )
    nao_examinadas = [p.numero for p in insp.paginas if p.tipo == TipoPagina.NAO_EXAMINADA]
    if nao_examinadas:
        insp.riscos.append(
            Risco(
                "PAGINAS_NAO_EXAMINADAS",
                f"{len(nao_examinadas)} página(s) não puderam ser examinadas.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
                detalhe="páginas: "
                + ", ".join(str(n + 1) for n in nao_examinadas[:20]),
            )
        )
    digitalizadas = insp.paginas_digitalizadas + insp.paginas_hibridas
    if digitalizadas:
        insp.riscos.append(
            Risco(
                "PAGINAS_DIGITALIZADAS",
                f"{digitalizadas} página(s) dependem de OCR para que o conteúdo seja "
                "examinado. A cobertura do OCR é limitada e deve ser conferida.",
                Severidade.AVISO,
            )
        )
