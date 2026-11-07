"""Orquestração do fluxo de trabalho.

Etapas, na ordem em que o usuário as percorre:

1. :meth:`Sessao.inspecionar` — inspeção estrutural dos PDFs selecionados;
2. :meth:`Sessao.analisar` — extração de texto, OCR local e detecção;
3. revisão humana (feita na interface, sobre o gerenciador de candidatos);
4. :meth:`Sessao.processar` — redação, limpeza, validação e relatório.

Todo o processamento ocorre com a rede bloqueada no processo (ver
:func:`anonimizador_dpu.core.security.rede_bloqueada`), de modo que qualquer
tentativa de acesso externo — própria ou de biblioteca de terceiros — falha de
forma visível em vez de transmitir conteúdo.
"""

from __future__ import annotations

import threading
from datetime import datetime
from pathlib import Path
from typing import Callable

import fitz

from .audit_logger import obter_logger
from .config import APP_VERSAO, Config
from .candidate_manager import GerenciadorCandidatos
from .entity_detector import candidatos_de_texto, detectar_na_pagina, papeis_profissionais_no_texto
from .models import (
    Candidato,
    Categoria,
    Inspecao,
    Origem,
    PaginaTexto,
    RelatorioDocumento,
    Risco,
    Severidade,
    Status,
    TipoPagina,
)
from .ocr_engine import ocr_pagina, verificar_ocr
from .output_validator import validar_saida
from .pdf_inspector import inspecionar
from .redaction_engine import aplicar_redacoes
from .report_generator import salvar_html, salvar_json
from .security import (
    ControleTempo,
    LimiteExcedido,
    destino_seguro,
    destino_sem_colisao,
    rede_bloqueada,
    validar_pdf_entrada,
)
from .text_extractor import (
    extrair_pagina,
    metadados_textuais,
    textos_de_anotacoes,
    textos_de_formulario,
    textos_de_links,
)

_log = obter_logger("pipeline")

Progresso = Callable[[str, int, int], None]


class Sessao:
    """Uma sessão de trabalho sobre um ou mais documentos do mesmo processo.

    Mantém em memória os textos extraídos e os candidatos. Nada é gravado em
    disco além dos arquivos de saída e dos relatórios solicitados.
    """

    def __init__(self, cfg: Config | None = None) -> None:
        self.cfg = cfg or Config()
        self.gerenciador = GerenciadorCandidatos()
        self.inspecoes: dict[str, Inspecao] = {}
        self.paginas: dict[str, list[PaginaTexto]] = {}
        self.arquivos: list[Path] = []
        self.relatorios: list[RelatorioDocumento] = []
        self.cancelar = threading.Event()
        self._avisos: dict[str, list[str]] = {}

    # ------------------------------------------------------------- utilidades
    def _cancelado(self) -> bool:
        return self.cancelar.is_set()

    def reiniciar_cancelamento(self) -> None:
        self.cancelar.clear()

    def limpar(self) -> None:
        """Descarta todo o conteúdo mantido em memória."""
        self.gerenciador.limpar()
        self.inspecoes.clear()
        self.paginas.clear()
        self.arquivos.clear()
        self.relatorios.clear()
        self._avisos.clear()

    # --------------------------------------------------------------- etapa 1
    def inspecionar(
        self, arquivos: list[str | Path], progresso: Progresso | None = None
    ) -> list[Inspecao]:
        """Inspeciona a estrutura de cada PDF selecionado, na ordem informada."""
        resultados: list[Inspecao] = []
        self.arquivos = []
        total = len(arquivos)
        with rede_bloqueada():
            for i, arquivo in enumerate(arquivos, start=1):
                if self._cancelado():
                    break
                if progresso:
                    progresso("Inspecionando documentos", i, total)
                caminho = Path(arquivo)
                insp = inspecionar(caminho, self.cfg)
                self.inspecoes[caminho.name] = insp
                self.arquivos.append(caminho)
                resultados.append(insp)
        return resultados

    # --------------------------------------------------------------- etapa 2
    def analisar(
        self, arquivo: str | Path, progresso: Progresso | None = None
    ) -> list[Candidato]:
        """Extrai texto, executa OCR local e detecta dados pessoais.

        O texto nativo e o texto de OCR são analisados separadamente, com origem
        distinta; a deduplicação ocorre no gerenciador de candidatos.
        """
        caminho = Path(arquivo)
        nome = caminho.name
        avisos = self._avisos.setdefault(nome, [])
        paginas_resultado: list[PaginaTexto] = []
        novos: list[Candidato] = []
        #: Nomes vistos com papel de profissional em algum ponto do documento.
        profissionais: set[str] = set()

        status_ocr = verificar_ocr(self.cfg.ocr)
        if self.cfg.ocr.habilitado and not status_ocr.disponivel:
            avisos.append(f"OCR indisponível: {status_ocr.erro}")

        tempo = ControleTempo(self.cfg.limites.timeout_documento_s)

        with rede_bloqueada():
            try:
                validar_pdf_entrada(caminho, self.cfg.limites.max_mb_arquivo)
                doc = fitz.open(caminho)
            except Exception as exc:
                avisos.append(f"Documento não pôde ser analisado: {exc}")
                self.paginas[nome] = []
                return []

            with doc:
                if doc.is_encrypted:
                    doc.authenticate("")
                total = doc.page_count
                insp = self.inspecoes.get(nome)

                for page in doc:
                    if self._cancelado():
                        avisos.append(
                            f"Análise cancelada na página {page.number + 1} de {total}."
                        )
                        break
                    try:
                        tempo.verificar()
                    except LimiteExcedido as exc:
                        avisos.append(str(exc))
                        break
                    if progresso:
                        progresso("Analisando páginas", page.number + 1, total)

                    pagina_texto = extrair_pagina(page)
                    tipo = (
                        insp.paginas[page.number].tipo
                        if insp and page.number < len(insp.paginas)
                        else TipoPagina.NAO_EXAMINADA
                    )

                    precisa_ocr = tipo in (
                        TipoPagina.DIGITALIZADA,
                        TipoPagina.HIBRIDA,
                        TipoPagina.NAO_EXAMINADA,
                    ) or not pagina_texto.texto_pdf.strip()

                    if precisa_ocr and self.cfg.ocr.habilitado and status_ocr.disponivel:
                        resultado_ocr = ocr_pagina(
                            page, self.cfg.ocr, self.cfg.limites.max_dimensao_render_px
                        )
                        pagina_texto.texto_ocr = resultado_ocr.texto_ocr
                        pagina_texto.palavras_ocr = resultado_ocr.palavras_ocr
                        pagina_texto.ocr_executado = resultado_ocr.ocr_executado
                        pagina_texto.ocr_confianca_media = resultado_ocr.ocr_confianca_media
                        pagina_texto.ocr_cobertura = resultado_ocr.ocr_cobertura
                        pagina_texto.ocr_falhou = resultado_ocr.ocr_falhou
                        pagina_texto.ocr_erro = resultado_ocr.ocr_erro
                        if resultado_ocr.observacao:
                            pagina_texto.observacao = resultado_ocr.observacao
                        pagina_texto.examinada = (
                            pagina_texto.examinada or resultado_ocr.examinada
                        )
                    elif precisa_ocr:
                        pagina_texto.observacao = (
                            "Página depende de OCR, que não foi executado. "
                            "Conteúdo não examinado."
                        )
                        pagina_texto.examinada = False

                    if tipo == TipoPagina.VAZIA and not pagina_texto.texto_pdf.strip():
                        pagina_texto.examinada = True
                        pagina_texto.observacao = "Página sem conteúdo extraível."

                    novos.extend(detectar_na_pagina(nome, pagina_texto, self.cfg))
                    novos.extend(self._candidatos_de_estruturas(nome, page))
                    # Quem é profissional em qualquer ponto do documento é a
                    # mesma pessoa nos demais. Ver `_aplicar_politica_de_papeis`.
                    for fonte in (pagina_texto.texto_pdf, pagina_texto.texto_ocr):
                        if fonte:
                            profissionais |= papeis_profissionais_no_texto(fonte, self.cfg)
                    paginas_resultado.append(pagina_texto)

                novos.extend(self._candidatos_de_metadados(nome, doc))

        self.paginas[nome] = paginas_resultado
        self.gerenciador.adicionar(novos)
        self._aplicar_politica_de_papeis(nome, profissionais, avisos)
        self.gerenciador.confirmar_automaticos(self.cfg.deteccao.limiar_auto_confirmacao)
        return self.gerenciador.por_documento(nome)

    def _aplicar_politica_de_papeis(
        self, nome: str, profissionais: set[str], avisos: list[str]
    ) -> None:
        """Aplica a política de profissionais **por pessoa**, não por ocorrência.

        O detector enxerga uma ocorrência por vez. O mesmo nome aparece
        rotulado num ponto ("RELATOR: JUIZ FEDERAL Fulano") e sem rótulo em
        outro ("assinado eletronicamente por Fulano"); a primeira era excluída
        pela política, a segunda era redigida. O resultado é o pior dos dois
        mundos: o nome continua legível no documento, a redação não protegeu
        ninguém e a validação independente reprova o arquivo — corretamente.
        """
        if self.cfg.deteccao.anonimizar_profissionais or not profissionais:
            return
        suprimidos = self.gerenciador.suprimir_por_valor(
            profissionais,
            documento=nome,
            motivo="Profissional identificado em outro ponto do documento; "
            "a política vigente não anonimiza profissionais.",
        )
        if suprimidos:
            avisos.append(
                f"{suprimidos} ocorrência(s) de nome mantidas no texto por serem de "
                "profissional (advogado, defensor, magistrado, perito ou servidor). "
                "Altere a política na aba de categorias se quiser anonimizá-las."
            )

    def _candidatos_de_estruturas(self, nome: str, page: fitz.Page) -> list[Candidato]:
        """Detecta dados pessoais em anotações, formulários e links da página."""
        encontrados: list[Candidato] = []
        fontes = (
            (textos_de_anotacoes(page), Origem.ANOTACAO),
            (textos_de_formulario(page), Origem.FORMULARIO),
            (textos_de_links(page), Origem.TEXTO),
        )
        for itens, origem in fontes:
            for texto, bbox in itens:
                encontrados.extend(
                    candidatos_de_texto(
                        nome,
                        page.number,
                        texto,
                        [],
                        origem,
                        self.cfg,
                        bboxes_fixas=[bbox],
                    )
                )
        return encontrados

    def _candidatos_de_metadados(self, nome: str, doc: fitz.Document) -> list[Candidato]:
        """Detecta dados pessoais nos metadados do documento.

        Metadados não possuem posição em página: as ocorrências são registradas
        para o relatório e tratadas pela limpeza de metadados, não pela redação
        geométrica.
        """
        encontrados: list[Candidato] = []
        for chave, valor in metadados_textuais(doc).items():
            for candidato in candidatos_de_texto(
                nome, 0, valor, [], Origem.METADADO, self.cfg, bboxes_fixas=[]
            ):
                candidato.motivo = f"Encontrado no metadado '{chave}'. " + candidato.motivo
                candidato.status = Status.CONFIRMADO
                candidato.requer_revisao = False
                candidato.bbox_incerta = False
                encontrados.append(candidato)
        return encontrados

    # --------------------------------------------------------------- etapa 4
    def paginas_para_reconstruir(self, nome: str) -> set[int]:
        """Páginas cuja estrutura exige reconstrução por renderização."""
        insp = self.inspecoes.get(nome)
        if insp is None:
            return set()
        if not insp.camadas_ocg:
            return set()
        return {p.numero for p in insp.paginas}

    def processar(
        self,
        arquivo: str | Path,
        pasta_saida: str | Path,
        progresso: Progresso | None = None,
        sobrescrever: bool = False,
        gerar_relatorios: bool = True,
    ) -> RelatorioDocumento:
        """Aplica a redação, valida o resultado e gera o relatório do documento."""
        caminho = Path(arquivo)
        nome = caminho.name
        relatorio = RelatorioDocumento(arquivo_entrada=nome, versao_app=APP_VERSAO)
        relatorio.inspecao = self.inspecoes.get(nome)
        relatorio.avisos = list(self._avisos.get(nome, []))

        paginas = self.paginas.get(nome, [])
        relatorio.paginas_por_texto = len([p for p in paginas if p.texto_pdf.strip()])
        relatorio.paginas_por_ocr = len([p for p in paginas if p.ocr_executado])
        relatorio.paginas_nao_examinadas = [p.numero for p in paginas if not p.examinada]

        candidatos = self.gerenciador.por_documento(nome)
        relatorio.candidatos = candidatos

        try:
            destino = destino_seguro(caminho, pasta_saida, self.cfg.sufixo_saida)
            if destino.exists() and not sobrescrever:
                destino = destino_sem_colisao(destino)
        except Exception as exc:
            relatorio.erro = str(exc)
            relatorio.fim = datetime.now()
            self.relatorios.append(relatorio)
            return relatorio

        with rede_bloqueada():
            resultado = aplicar_redacoes(
                caminho,
                destino,
                candidatos,
                self.cfg,
                paginas_para_reconstruir=self.paginas_para_reconstruir(nome),
                progresso=progresso,
                cancelado=self._cancelado,
            )
            relatorio.redacao = resultado
            relatorio.arquivo_saida = str(destino)

            if resultado.cancelado:
                relatorio.cancelado = True
                relatorio.erro = (
                    "Processamento cancelado pelo usuário. O documento de saída não "
                    "pode ser considerado pronto."
                )
                relatorio.fim = datetime.now()
                self.relatorios.append(relatorio)
                return relatorio

            if not destino.exists():
                relatorio.erro = "O documento de saída não foi gravado."
                relatorio.fim = datetime.now()
                self.relatorios.append(relatorio)
                return relatorio

            relatorio.validacao = validar_saida(
                destino,
                self.cfg,
                candidatos,
                inspecao_entrada=relatorio.inspecao,
                redacao=resultado,
                progresso=progresso,
                cancelado=self._cancelado,
            )

        relatorio.fim = datetime.now()

        if gerar_relatorios:
            base = destino.with_suffix("")
            try:
                salvar_json(relatorio, self.cfg, Path(f"{base}_relatorio.json"))
                salvar_html(relatorio, self.cfg, Path(f"{base}_relatorio.html"))
            except OSError as exc:
                relatorio.avisos.append(f"Falha ao gravar relatório: {exc}")

        self.relatorios.append(relatorio)
        _log.info(
            "Documento processado: veredito=%s.", relatorio.veredito.value
        )
        return relatorio

    # -------------------------------------------------------------- em lote
    def processar_lote(
        self,
        pasta_saida: str | Path,
        progresso: Progresso | None = None,
        sobrescrever: bool = False,
    ) -> list[RelatorioDocumento]:
        """Processa todos os documentos da sessão, preservando a ordem."""
        saida: list[RelatorioDocumento] = []
        total = len(self.arquivos)
        for i, arquivo in enumerate(self.arquivos, start=1):
            if self._cancelado():
                break
            if progresso:
                progresso(f"Documento {i} de {total}", i, total)
            saida.append(
                self.processar(
                    arquivo, pasta_saida, progresso=progresso, sobrescrever=sobrescrever
                )
            )
        return saida

    # ------------------------------------------------------------- consultas
    def risco_global(self) -> list[Risco]:
        riscos: list[Risco] = []
        for insp in self.inspecoes.values():
            riscos.extend(insp.riscos)
        return riscos

    def adicionar_regiao_manual(
        self, documento: str, pagina: int, bbox: tuple[float, float, float, float]
    ) -> Candidato:
        """Marca uma região retangular de uma página para redação."""
        return self.gerenciador.adicionar_manual(
            documento, pagina, Categoria.REGIAO_MANUAL, "[região marcada]", [bbox]
        )
