"""Validação independente do PDF anonimizado.

A validação roda sobre o arquivo **gravado**, reaberto do disco, e não reaproveita
nenhuma estrutura em memória produzida pelo mecanismo de redação. Ela repete a
extração de texto, o OCR e a detecção, confere as áreas redigidas, examina
metadados e anexos e procura os identificadores originais conhecidos da sessão.

Princípio: a ausência de resultado nos detectores NÃO prova anonimização
integral. Por isso o veredito considera também a cobertura do exame (páginas
efetivamente examinadas) e as estruturas não tratadas.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Callable

import fitz

from .attachment_inspector import anexos_residuais
from .audit_logger import obter_logger
from .brazilian_validators import somente_digitos
from .config import Config
from .entity_detector import detectar
from .metadata_cleaner import metadados_residuais
from .models import (
    Candidato,
    Categoria,
    Inspecao,
    Origem,
    ResultadoRedacao,
    ResultadoValidacao,
    Risco,
    Severidade,
    Status,
    TipoPagina,
    Veredito,
)
from .ocr_engine import ocr_pagina, verificar_ocr

_log = obter_logger("validador")

Progresso = Callable[[str, int, int], None]
Cancelado = Callable[[], bool]


def _normalizar(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def _minusculo(texto: str) -> str:
    """Como :func:`_normalizar`, mas preservando os acentos."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", texto)).strip().lower()


def _palavra_presente(alvo: str, texto: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(alvo) + r"(?!\w)", texto) is not None


def _valor_presente(
    valor: str, texto_normalizado: str, digitos_texto: str, texto_minusculo: str = ""
) -> bool:
    """Procura um identificador conhecido no texto de saída.

    Números são comparados pelos dígitos (ignorando pontuação); textos são
    comparados sem acentos e sem diferença de caixa, como palavra inteira.

    Exceção: uma palavra só, com acento, é comparada **com** o acento. Sem o
    acento, a localidade "PARÁ" é a preposição "para", e reprovava todo
    documento do Pará. Nome de mais de uma palavra não corre esse risco e
    continua comparado sem acento, que tolera o OCR que perde o acento.
    """
    alvo = valor.strip()
    if len(alvo) < 4:
        return False
    digitos = somente_digitos(alvo)
    if digitos and len(digitos) >= 6:
        return digitos in digitos_texto
    normalizado = _normalizar(alvo)
    tem_acento = normalizado != _minusculo(alvo)
    if texto_minusculo and tem_acento and " " not in normalizado:
        return _palavra_presente(_minusculo(alvo), texto_minusculo)
    return _palavra_presente(normalizado, texto_normalizado)


def validar_saida(
    saida: Path,
    cfg: Config,
    candidatos_sessao: list[Candidato],
    inspecao_entrada: Inspecao | None = None,
    redacao: ResultadoRedacao | None = None,
    progresso: Progresso | None = None,
    cancelado: Cancelado | None = None,
) -> ResultadoValidacao:
    """Executa a validação completa do documento de saída."""
    resultado = ResultadoValidacao()

    try:
        doc = fitz.open(saida)
    except Exception as exc:
        resultado.abriu_corretamente = False
        resultado.riscos.append(
            Risco(
                "SAIDA_ILEGIVEL",
                "O documento anonimizado não pôde ser reaberto.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
                detalhe=str(exc)[:200],
            )
        )
        resultado.veredito = Veredito.REPROVADO
        return resultado

    valores_conhecidos = {
        c.valor
        for c in candidatos_sessao
        if c.status in (Status.REDIGIDO, Status.CONFIRMADO, Status.VERIFICADO)
    }
    # Ocorrência que o revisor (ou a política) decidiu manter no texto não é
    # falha: encontrá-la na saída é o resultado esperado. Sem isto, o nome do
    # magistrado, deliberadamente preservado, voltava como pendência.
    valores_mantidos = {
        _normalizar(c.valor)
        for c in candidatos_sessao
        if c.status is Status.REJEITADO and c.valor
    }
    valores_conhecidos = {
        v for v in valores_conhecidos if _normalizar(v) not in valores_mantidos
    }
    status_ocr = verificar_ocr(cfg.ocr)

    with doc:
        resultado.abriu_corretamente = True
        total = doc.page_count

        for page in doc:
            if cancelado and cancelado():
                resultado.riscos.append(
                    Risco(
                        "VALIDACAO_CANCELADA",
                        "A validação foi cancelada antes de examinar todas as páginas.",
                        Severidade.CRITICO,
                        bloqueia_aprovacao=True,
                    )
                )
                resultado.veredito = Veredito.REPROVADO
                return resultado
            if progresso:
                progresso("Validando documento", page.number + 1, total)

            texto = page.get_text("text") or ""
            resultado.paginas_verificadas_texto += 1
            texto_normalizado = _normalizar(texto)
            texto_minusculo = _minusculo(texto)
            digitos_texto = somente_digitos(texto)

            # 1. detectores sobre o texto da saída
            for achado in detectar(texto, cfg):
                if _normalizar(achado.valor) in valores_mantidos:
                    continue
                resultado.residuais.append(
                    Candidato(
                        documento=saida.name,
                        pagina=page.number,
                        categoria=achado.categoria,
                        valor=achado.valor,
                        origem=Origem.TEXTO,
                        status=Status.FALHA_CRITICA,
                        confianca=achado.confianca,
                        detector=f"validacao:{achado.detector}",
                        motivo="Ocorrência detectada no documento de saída",
                    )
                )

            # 2. identificadores originais conhecidos
            for valor in valores_conhecidos:
                if _valor_presente(valor, texto_normalizado, digitos_texto, texto_minusculo):
                    resultado.residuais_conhecidos += 1
                    resultado.riscos.append(
                        Risco(
                            "IDENTIFICADOR_RESIDUAL",
                            "Identificador originalmente confirmado para redação ainda "
                            "é recuperável no texto do documento de saída.",
                            Severidade.CRITICO,
                            pagina=page.number,
                            bloqueia_aprovacao=True,
                        )
                    )

            # 3. OCR de verificação nas páginas com conteúdo visual
            precisa_ocr = _pagina_tem_imagem(page)
            if precisa_ocr and cfg.ocr.habilitado and status_ocr.disponivel:
                pagina_ocr = ocr_pagina(page, cfg.ocr, cfg.limites.max_dimensao_render_px)
                resultado.paginas_verificadas_ocr += 1
                if pagina_ocr.ocr_falhou:
                    resultado.paginas_sem_cobertura.append(page.number)
                    resultado.riscos.append(
                        Risco(
                            "OCR_VALIDACAO_FALHOU",
                            "O OCR de verificação falhou nesta página do documento de saída.",
                            Severidade.CRITICO,
                            pagina=page.number,
                            bloqueia_aprovacao=True,
                            detalhe=pagina_ocr.ocr_erro[:200],
                        )
                    )
                else:
                    if not pagina_ocr.examinada:
                        resultado.paginas_sem_cobertura.append(page.number)
                    texto_ocr = pagina_ocr.texto_ocr
                    ocr_normalizado = _normalizar(texto_ocr)
                    ocr_minusculo = _minusculo(texto_ocr)
                    ocr_digitos = somente_digitos(texto_ocr)
                    for achado in detectar(texto_ocr, cfg):
                        if _normalizar(achado.valor) in valores_mantidos:
                            continue
                        resultado.residuais.append(
                            Candidato(
                                documento=saida.name,
                                pagina=page.number,
                                categoria=achado.categoria,
                                valor=achado.valor,
                                origem=Origem.OCR,
                                status=Status.FALHA_CRITICA,
                                confianca=achado.confianca,
                                detector=f"validacao_ocr:{achado.detector}",
                                motivo="Ocorrência detectada por OCR no documento de saída",
                            )
                        )
                    for valor in valores_conhecidos:
                        if _valor_presente(valor, ocr_normalizado, ocr_digitos, ocr_minusculo):
                            resultado.residuais_conhecidos += 1
                            resultado.riscos.append(
                                Risco(
                                    "IDENTIFICADOR_RESIDUAL_IMAGEM",
                                    "Identificador confirmado para redação continua "
                                    "legível na imagem da página de saída.",
                                    Severidade.CRITICO,
                                    pagina=page.number,
                                    bloqueia_aprovacao=True,
                                )
                            )
            elif precisa_ocr:
                resultado.paginas_sem_cobertura.append(page.number)
                resultado.riscos.append(
                    Risco(
                        "SEM_OCR_VALIDACAO",
                        "Página com conteúdo de imagem não pôde ser verificada por OCR "
                        f"({status_ocr.erro or 'OCR desabilitado'}).",
                        Severidade.CRITICO,
                        pagina=page.number,
                        bloqueia_aprovacao=True,
                    )
                )

        # 4. áreas de redação
        _conferir_areas_redigidas(doc, candidatos_sessao, resultado)

        # 5. metadados e anexos
        resultado.metadados_residuais = metadados_residuais(doc)
        if resultado.metadados_residuais:
            resultado.riscos.append(
                Risco(
                    "METADADOS_RESIDUAIS",
                    "O documento de saída ainda possui metadados preenchidos: "
                    + ", ".join(resultado.metadados_residuais),
                    Severidade.AVISO,
                )
            )
        resultado.anexos_residuais = anexos_residuais(doc)
        if resultado.anexos_residuais:
            resultado.riscos.append(
                Risco(
                    "ANEXOS_RESIDUAIS",
                    f"O documento de saída ainda contém {len(resultado.anexos_residuais)} "
                    "arquivo(s) incorporado(s), cujo conteúdo não foi analisado.",
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                )
            )
        try:
            if doc.get_ocgs():
                resultado.riscos.append(
                    Risco(
                        "CAMADAS_RESIDUAIS",
                        "O documento de saída mantém camadas de conteúdo opcional.",
                        Severidade.CRITICO,
                        bloqueia_aprovacao=True,
                    )
                )
        except Exception:  # pragma: no cover
            pass

    _agregar_riscos_externos(resultado, candidatos_sessao, inspecao_entrada, redacao)
    resultado.veredito = decidir_veredito(resultado, cfg, candidatos_sessao)
    _log.info(
        "Validação concluída: veredito=%s, residuais detectados=%d, conhecidos=%d.",
        resultado.veredito.value,
        len(resultado.residuais),
        resultado.residuais_conhecidos,
    )
    return resultado


def _pagina_tem_imagem(page: fitz.Page) -> bool:
    try:
        return bool(page.get_images(full=True))
    except Exception:  # pragma: no cover
        return True


def _conferir_areas_redigidas(
    doc: fitz.Document, candidatos: list[Candidato], resultado: ResultadoValidacao
) -> None:
    """Confere, área por área, se o conteúdo original deixou de ser extraível."""
    from .image_redaction import area_contem_conteudo  # import local: evita ciclo

    for candidato in candidatos:
        if candidato.status not in (Status.REDIGIDO, Status.VERIFICADO):
            continue
        if candidato.pagina >= doc.page_count:
            continue
        page = doc[candidato.pagina]
        falhou = False
        for bbox in candidato.bboxes:
            resultado.areas_redacao_conferidas += 1
            restante = page.get_textbox(fitz.Rect(bbox)).strip()
            if candidato.valor.strip() and candidato.valor.strip() in restante:
                falhou = True
                break
            # Uma área que continua com variação de pixels sugere conteúdo visível.
            if candidato.origem in (Origem.OCR, Origem.TEXTO_E_OCR) and area_contem_conteudo(
                page, bbox
            ):
                # O pseudônimo escrito por cima também gera variação: só é falha
                # quando nenhum texto substituto foi aplicado.
                if not restante:
                    falhou = True
                    break
        if falhou:
            resultado.areas_redacao_falhas.append(candidato.pagina)
            candidato.status = Status.FALHA_CRITICA
            candidato.falha = "Conferência da área redigida indicou conteúdo remanescente."
            resultado.riscos.append(
                Risco(
                    "AREA_NAO_LIMPA",
                    "Área redigida ainda apresenta conteúdo recuperável ou visível.",
                    Severidade.CRITICO,
                    pagina=candidato.pagina,
                    bloqueia_aprovacao=True,
                )
            )
        else:
            candidato.status = Status.VERIFICADO


def _agregar_riscos_externos(
    resultado: ResultadoValidacao,
    candidatos: list[Candidato],
    inspecao: Inspecao | None,
    redacao: ResultadoRedacao | None,
) -> None:
    """Traz para a validação os riscos herdados da inspeção e da redação."""
    if inspecao is not None:
        for risco in inspecao.riscos:
            if risco.bloqueia_aprovacao:
                resultado.riscos.append(risco)
        nao_examinadas = [
            p.numero for p in inspecao.paginas if p.tipo == TipoPagina.NAO_EXAMINADA
        ]
        for numero in nao_examinadas:
            if numero not in resultado.paginas_sem_cobertura:
                resultado.paginas_sem_cobertura.append(numero)
    if redacao is not None:
        resultado.riscos.extend(redacao.falhas)
        if redacao.estruturas_nao_tratadas:
            resultado.riscos.append(
                Risco(
                    "ESTRUTURAS_NAO_TRATADAS",
                    "Estruturas internas não tratadas: "
                    + "; ".join(redacao.estruturas_nao_tratadas[:5]),
                    Severidade.CRITICO,
                    bloqueia_aprovacao=True,
                )
            )
        if redacao.paginas_rasterizadas:
            resultado.observacoes.append(
                f"{len(redacao.paginas_rasterizadas)} página(s) foram reconstruídas por "
                "renderização: o texto deixou de ser selecionável e links, formulários "
                "e assinaturas foram perdidos."
            )

    pendentes = [
        c
        for c in candidatos
        if c.status in (Status.PENDENTE, Status.DETECTADO) or c.requer_revisao
    ]
    if pendentes:
        resultado.riscos.append(
            Risco(
                "OCORRENCIAS_PENDENTES",
                f"{len(pendentes)} ocorrência(s) não receberam decisão humana.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )
    falhas = [c for c in candidatos if c.status == Status.FALHA_CRITICA]
    if falhas:
        resultado.riscos.append(
            Risco(
                "FALHAS_DE_REDACAO",
                f"{len(falhas)} ocorrência(s) confirmada(s) não foram redigidas com segurança.",
                Severidade.CRITICO,
                bloqueia_aprovacao=True,
            )
        )


def decidir_veredito(
    resultado: ResultadoValidacao, cfg: Config, candidatos: list[Candidato]
) -> Veredito:
    """Classifica o documento, bloqueando a aprovação diante de falha crítica.

    Nenhuma configuração permite ignorar um bloqueio crítico: a opção de
    "aprovado com ressalvas" só alcança avisos.
    """
    if not resultado.abriu_corretamente:
        return Veredito.REPROVADO
    if resultado.residuais_conhecidos > 0 or resultado.areas_redacao_falhas:
        return Veredito.REPROVADO
    if any(c.status == Status.FALHA_CRITICA for c in candidatos):
        return Veredito.REPROVADO
    if resultado.residuais:
        # Ocorrências detectadas na saída: podem ser dados não confirmados pelo
        # usuário (falso negativo da revisão) — exigem decisão humana.
        return Veredito.REVISAO_OBRIGATORIA

    bloqueios = [r for r in resultado.riscos if r.bloqueia_aprovacao]
    if bloqueios:
        criticos = [r for r in bloqueios if r.severidade == Severidade.CRITICO]
        if any(
            r.codigo
            in (
                "IDENTIFICADOR_RESIDUAL",
                "IDENTIFICADOR_RESIDUAL_IMAGEM",
                "AREA_NAO_LIMPA",
                "TEXTO_RESIDUAL_AREA",
                "FALHA_APLICACAO",
                "FALHA_GRAVACAO",
                "SAIDA_ILEGIVEL",
            )
            for r in criticos
        ):
            return Veredito.REPROVADO
        return Veredito.REVISAO_OBRIGATORIA

    if resultado.paginas_sem_cobertura:
        return Veredito.REVISAO_OBRIGATORIA

    avisos = [r for r in resultado.riscos if r.severidade == Severidade.AVISO]
    if avisos:
        if cfg.permitir_aprovacao_com_ressalvas:
            return Veredito.APROVADO_COM_RESSALVAS
        return Veredito.REVISAO_OBRIGATORIA

    return Veredito.APROVADO_TESTES
