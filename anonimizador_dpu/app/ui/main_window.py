"""Janela principal do Anonimizador DPU.

O fluxo é apresentado em etapas numeradas, na ordem em que devem ser cumpridas.
Nenhuma etapa posterior libera o documento como aprovado antes que as
verificações obrigatórias tenham sido concluídas.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QAction, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QPlainTextEdit,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ...core.config import (
    APP_NOME,
    APP_VERSAO,
    AVISO_ASSINATURA,
    AVISO_PRINCIPAL,
    AVISO_SSD,
    Config,
)
from ...core.models import (
    CATEGORIAS_INFO,
    ROTULOS_VEREDITO,
    Categoria,
    Grupo,
    RelatorioDocumento,
    Severidade,
    Status,
    Veredito,
    rotulo_categoria,
)
from ...core.ocr_engine import descrever_ambiente_ocr, verificar_ocr
from ...core.pipeline import Sessao
from .page_viewer import VisualizadorPagina
from .review_panel import PainelRevisao
from .tema import (
    cores_html,
    cores_veredito,
    estilo_aviso,
    estilo_botao_principal,
)
from .workers import WorkerAnalise, WorkerInspecao, WorkerProcessamento

ROTULOS_GRUPO = {
    Grupo.A_IDENTIFICACAO: "A — Identificação pessoal",
    Grupo.B_CONTATO_LOCALIZACAO: "B — Contato e localização",
    Grupo.C_FINANCEIRO: "C — Dados financeiros",
    Grupo.D_PROCESSUAL: "D — Identificadores processuais",
    Grupo.E_PESSOAS_RELACIONADAS: "E — Pessoas relacionadas",
    Grupo.F_SENSIVEL: "F — Dados pessoais sensíveis",
    Grupo.G_ANEXOS: "G — Elementos em anexos",
    Grupo.H_OUTROS: "H — Outros identificadores",
}

#: As cores de veredito dependem do tema ativo (ver ``tema.cores_veredito``).


class JanelaPrincipal(QMainWindow):
    def __init__(self, cfg: Config | None = None) -> None:
        super().__init__()
        self.cfg = cfg or Config.carregar()
        self.sessao = Sessao(self.cfg)
        self.worker = None
        self.pasta_saida: Path | None = (
            Path(self.cfg.pasta_saida_padrao) if self.cfg.pasta_saida_padrao else None
        )

        self.setWindowTitle(f"{APP_NOME} {APP_VERSAO}")
        # No Mac a fonte do sistema é maior; 1440 pontos de largura dão à aba
        # de revisão o mesmo respiro que 1280 dão no Windows e cabem na tela
        # de qualquer MacBook com chip Apple (ver também _caber_na_tela).
        self.resize(1440 if sys.platform == "darwin" else 1280, 820)
        self._montar()
        self._montar_menu()
        self._atualizar_estado_ocr()
        self._atualizar_rotulo_saida()
        if sys.platform == "darwin":
            self._caber_na_tela()

    def _caber_na_tela(self) -> None:
        """No Mac, a janela inicial não passa da área útil da tela.

        Em notebooks pequenos com o Dock à mostra, 820 pontos de altura (mais a
        barra de título) deixariam o rodapé da janela escondido atrás do Dock.
        """
        tela = self.screen().availableGeometry()
        barra_de_titulo = 28
        self.resize(
            min(self.width(), tela.width()),
            min(self.height(), tela.height() - barra_de_titulo),
        )

    # ------------------------------------------------------------- construção
    def _montar(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        aviso = QLabel(f"⚠ {AVISO_PRINCIPAL}")
        aviso.setWordWrap(True)
        aviso.setStyleSheet(estilo_aviso())
        layout.addWidget(aviso)

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_documentos(), "1 · Documentos")
        self.abas.addTab(self._aba_inspecao(), "2 · Inspeção")
        self.abas.addTab(self._aba_categorias(), "3 · Categorias")
        self.abas.addTab(self._aba_revisao(), "4 · Revisão")
        self.abas.addTab(self._aba_resultado(), "5 · Resultado")
        layout.addWidget(self.abas, 1)

        rodape = QHBoxLayout()
        self.barra = QProgressBar()
        self.barra.setFormat("%v de %m — %p%")
        self.bt_cancelar = QPushButton("Cancelar operação")
        self.bt_cancelar.setEnabled(False)
        self.bt_cancelar.clicked.connect(self._cancelar)
        rodape.addWidget(self.barra, 1)
        rodape.addWidget(self.bt_cancelar)
        layout.addLayout(rodape)

        self.setCentralWidget(central)
        self.statusBar().showMessage("Pronto.")

    def _montar_menu(self) -> None:
        menu_arquivo = self.menuBar().addMenu("&Arquivo")
        a_abrir = QAction("Selecionar PDFs…", self)
        a_abrir.triggered.connect(self._selecionar_arquivos)
        menu_arquivo.addAction(a_abrir)
        a_pasta = QAction("Selecionar pasta de saída…", self)
        a_pasta.triggered.connect(self._selecionar_pasta)
        menu_arquivo.addAction(a_pasta)
        if sys.platform != "darwin":
            # No Mac, "Sair" migra para o menu do aplicativo (abaixo), e o
            # separador ficaria sobrando no fim do menu Arquivo.
            menu_arquivo.addSeparator()
        a_sair = QAction("Sair", self)
        a_sair.triggered.connect(self.close)
        menu_arquivo.addAction(a_sair)

        menu_ferramentas = self.menuBar().addMenu("&Ferramentas")
        a_ocr = QAction("Verificar OCR local…", self)
        a_ocr.triggered.connect(self._verificar_ocr)
        menu_ferramentas.addAction(a_ocr)
        a_salvar = QAction("Salvar configuração", self)
        a_salvar.triggered.connect(self._salvar_config)
        menu_ferramentas.addAction(a_salvar)

        menu_ajuda = self.menuBar().addMenu("A&juda")
        a_limites = QAction("Limitações e riscos…", self)
        a_limites.triggered.connect(self._mostrar_limitacoes)
        menu_ajuda.addAction(a_limites)
        a_sobre = QAction("Sobre", self)
        a_sobre.triggered.connect(self._mostrar_sobre)
        menu_ajuda.addAction(a_sobre)

        # No Mac, "Sair" e "Sobre" vão para o menu do aplicativo, como em todo
        # programa do sistema (com o atalho Cmd+Q para sair). Os demais itens
        # ficam explicitamente onde estão: sem isso, o Qt adivinha pelo texto
        # e poderia mover algum deles. Nas outras plataformas, nada muda.
        for acao in (a_abrir, a_pasta, a_ocr, a_salvar, a_limites):
            acao.setMenuRole(QAction.MenuRole.NoRole)
        a_sair.setMenuRole(QAction.MenuRole.QuitRole)
        a_sobre.setMenuRole(QAction.MenuRole.AboutRole)

    # ------------------------------------------------------------ aba 1
    def _aba_documentos(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)

        layout.addWidget(
            QLabel(
                "Selecione os PDFs do mesmo processo. O arquivo original nunca é "
                "alterado: os resultados são gravados em pasta separada."
            )
        )

        self.lista_arquivos = QListWidget()
        self.lista_arquivos.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection
        )
        layout.addWidget(self.lista_arquivos, 1)

        botoes = QHBoxLayout()
        bt_add = QPushButton("Adicionar PDFs…")
        bt_add.clicked.connect(self._selecionar_arquivos)
        bt_rem = QPushButton("Remover selecionados")
        bt_rem.clicked.connect(self._remover_arquivos)
        bt_limpar = QPushButton("Limpar sessão")
        bt_limpar.clicked.connect(self._limpar_sessao)
        botoes.addWidget(bt_add)
        botoes.addWidget(bt_rem)
        botoes.addWidget(bt_limpar)
        botoes.addStretch(1)
        layout.addLayout(botoes)

        saida = QHBoxLayout()
        self.lb_saida = QLabel("Pasta de saída: (não selecionada)")
        bt_saida = QPushButton("Selecionar pasta de saída…")
        bt_saida.clicked.connect(self._selecionar_pasta)
        saida.addWidget(self.lb_saida, 1)
        saida.addWidget(bt_saida)
        layout.addLayout(saida)

        self.chk_sobrescrever = QCheckBox(
            "Permitir sobrescrever arquivos de mesmo nome na pasta de saída"
        )
        layout.addWidget(self.chk_sobrescrever)

        self.lb_ocr = QLabel()
        self.lb_ocr.setWordWrap(True)
        layout.addWidget(self.lb_ocr)

        self.bt_inspecionar = QPushButton("Inspecionar documentos ▶")
        self.bt_inspecionar.clicked.connect(self._inspecionar)
        self.bt_inspecionar.setStyleSheet(estilo_botao_principal())
        self.bt_inspecionar.setMinimumHeight(44)
        layout.addWidget(self.bt_inspecionar)
        return aba

    # ------------------------------------------------------------ aba 2
    def _aba_inspecao(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        self.txt_inspecao = QTextBrowser()
        self.txt_inspecao.setOpenExternalLinks(False)
        layout.addWidget(self.txt_inspecao, 1)
        self.bt_analisar = QPushButton("Extrair texto, executar OCR e detectar dados ▶")
        self.bt_analisar.clicked.connect(self._analisar)
        self.bt_analisar.setEnabled(False)
        self.bt_analisar.setStyleSheet(estilo_botao_principal())
        self.bt_analisar.setMinimumHeight(44)
        layout.addWidget(self.bt_analisar)
        return aba

    # ------------------------------------------------------------ aba 3
    def _aba_categorias(self) -> QWidget:
        aba = QWidget()
        externo = QVBoxLayout(aba)
        area = QScrollArea()
        area.setWidgetResizable(True)
        conteudo = QWidget()
        layout = QVBoxLayout(conteudo)

        self.checks_categoria: dict[Categoria, QCheckBox] = {}
        por_grupo: dict[Grupo, list[Categoria]] = {}
        for categoria, (_, grupo, _) in CATEGORIAS_INFO.items():
            por_grupo.setdefault(grupo, []).append(categoria)

        for grupo, categorias in por_grupo.items():
            caixa = QGroupBox(ROTULOS_GRUPO.get(grupo, grupo.value))
            interno = QVBoxLayout(caixa)
            for categoria in categorias:
                chk = QCheckBox(rotulo_categoria(categoria))
                chk.setChecked(self.cfg.categoria_ativa(categoria))
                chk.toggled.connect(
                    lambda ativo, c=categoria: self.cfg.ativar(c, ativo)
                )
                interno.addWidget(chk)
                self.checks_categoria[categoria] = chk
            layout.addWidget(caixa)

        politica = QGroupBox("Política de anonimização")
        form = QFormLayout(politica)

        self.chk_confirmar_padrao = QCheckBox(
            "Marcar tudo para remoção por padrão (o revisor desmarca o que deve ficar)"
        )
        self.chk_confirmar_padrao.setChecked(self.cfg.deteccao.confirmar_por_padrao)
        self.chk_confirmar_padrao.setToolTip(
            "Ligado: toda ocorrência detectada já entra marcada e será removida.\n"
            "Desligado: cada ocorrência precisa ser confirmada individualmente."
        )
        self.chk_confirmar_padrao.toggled.connect(
            lambda v: setattr(self.cfg.deteccao, "confirmar_por_padrao", v)
        )
        form.addRow(self.chk_confirmar_padrao)

        self.chk_profissionais = QCheckBox(
            "Anonimizar também advogados, defensores, magistrados, peritos e servidores"
        )
        self.chk_profissionais.setChecked(self.cfg.deteccao.anonimizar_profissionais)
        self.chk_profissionais.toggled.connect(
            lambda v: setattr(self.cfg.deteccao, "anonimizar_profissionais", v)
        )
        form.addRow(self.chk_profissionais)

        self.cb_modo = QComboBox()
        self.cb_modo.addItem("Substituir por pseudônimo (preserva a leitura)", "pseudonimo")
        self.cb_modo.addItem("Tarja sólida (sem rótulo)", "tarja")
        self.cb_modo.setCurrentIndex(0 if self.cfg.redacao.modo == "pseudonimo" else 1)
        self.cb_modo.currentIndexChanged.connect(
            lambda: setattr(self.cfg.redacao, "modo", self.cb_modo.currentData())
        )
        form.addRow("Modo de redação:", self.cb_modo)

        self.sp_auto = QDoubleSpinBox()
        self.sp_auto.setRange(0.5, 1.0)
        self.sp_auto.setSingleStep(0.01)
        self.sp_auto.setValue(self.cfg.deteccao.limiar_auto_confirmacao)
        self.sp_auto.valueChanged.connect(
            lambda v: setattr(self.cfg.deteccao, "limiar_auto_confirmacao", v)
        )
        form.addRow("Confiança mínima para confirmação automática:", self.sp_auto)

        self.sp_revisao = QDoubleSpinBox()
        self.sp_revisao.setRange(0.1, 1.0)
        self.sp_revisao.setSingleStep(0.01)
        self.sp_revisao.setValue(self.cfg.deteccao.limiar_revisao_obrigatoria)
        self.sp_revisao.valueChanged.connect(
            lambda v: setattr(self.cfg.deteccao, "limiar_revisao_obrigatoria", v)
        )
        form.addRow("Abaixo desta confiança, decisão humana obrigatória:", self.sp_revisao)

        self.cb_idiomas = QComboBox()
        self.cb_idiomas.addItem("Português", "por")
        self.cb_idiomas.addItem("Português + Inglês", "por+eng")
        self.cb_idiomas.setCurrentIndex(0 if self.cfg.ocr.idiomas == "por" else 1)
        self.cb_idiomas.currentIndexChanged.connect(
            lambda: setattr(self.cfg.ocr, "idiomas", self.cb_idiomas.currentData())
        )
        form.addRow("Idiomas do OCR:", self.cb_idiomas)

        self.sp_dpi = QSpinBox()
        self.sp_dpi.setRange(150, 600)
        self.sp_dpi.setSingleStep(50)
        self.sp_dpi.setValue(self.cfg.ocr.dpi)
        self.sp_dpi.valueChanged.connect(lambda v: setattr(self.cfg.ocr, "dpi", v))
        form.addRow("Resolução do OCR (DPI):", self.sp_dpi)

        self.chk_ocr = QCheckBox("Executar OCR local nas páginas digitalizadas")
        self.chk_ocr.setChecked(self.cfg.ocr.habilitado)
        self.chk_ocr.toggled.connect(lambda v: setattr(self.cfg.ocr, "habilitado", v))
        form.addRow(self.chk_ocr)

        self.chk_ressalvas = QCheckBox(
            "A política institucional admite o resultado 'APROVADO COM RESSALVAS'"
        )
        self.chk_ressalvas.setChecked(self.cfg.permitir_aprovacao_com_ressalvas)
        self.chk_ressalvas.toggled.connect(
            lambda v: setattr(self.cfg, "permitir_aprovacao_com_ressalvas", v)
        )
        form.addRow(self.chk_ressalvas)

        layout.addWidget(politica)

        termos = QGroupBox("Termos da sua unidade (um por linha)")
        form_termos = QFormLayout(termos)

        self.ed_personalizados = QPlainTextEdit()
        self.ed_personalizados.setPlaceholderText(
            "Nomes ou expressões que devem SEMPRE ser removidos, mesmo que a "
            "detecção automática não os encontre."
        )
        self.ed_personalizados.setPlainText(
            "\n".join(self.cfg.deteccao.termos_personalizados)
        )
        self.ed_personalizados.setMaximumHeight(90)
        form_termos.addRow("Sempre remover:", self.ed_personalizados)

        self.ed_ignorados = QPlainTextEdit()
        self.ed_ignorados.setPlaceholderText(
            "Expressões que NUNCA devem ser tratadas como dado pessoal — use "
            "para eliminar falsos positivos recorrentes na sua matéria."
        )
        self.ed_ignorados.setPlainText("\n".join(self.cfg.deteccao.termos_ignorados))
        self.ed_ignorados.setMaximumHeight(90)
        form_termos.addRow("Nunca remover:", self.ed_ignorados)

        for editor, campo in (
            (self.ed_personalizados, "termos_personalizados"),
            (self.ed_ignorados, "termos_ignorados"),
        ):
            editor.textChanged.connect(
                lambda e=editor, c=campo: setattr(
                    self.cfg.deteccao,
                    c,
                    [t.strip() for t in e.toPlainText().splitlines() if t.strip()],
                )
            )

        layout.addWidget(termos)
        layout.addStretch(1)
        area.setWidget(conteudo)
        externo.addWidget(area, 1)

        bt_salvar = QPushButton("Salvar configuração")
        bt_salvar.clicked.connect(self._salvar_config)
        externo.addWidget(bt_salvar)
        return aba

    # ------------------------------------------------------------ aba 4
    def _aba_revisao(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)

        topo = QHBoxLayout()
        topo.addWidget(QLabel("Documento:"))
        self.cb_documento = QComboBox()
        self.cb_documento.currentIndexChanged.connect(self._trocar_documento)
        topo.addWidget(self.cb_documento, 1)
        layout.addLayout(topo)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        self.painel_revisao = PainelRevisao(self.sessao.gerenciador, self.cfg)
        self.painel_revisao.ocorrencia_selecionada.connect(self._mostrar_pagina)
        self.painel_revisao.marcar_regiao_solicitada.connect(self._ativar_marcacao)
        self.painel_revisao.alteracoes.connect(self._atualizar_visualizador)
        divisor.addWidget(self.painel_revisao)

        direita = QWidget()
        col = QVBoxLayout(direita)
        self.visualizador = VisualizadorPagina()
        if sys.platform == "darwin":
            # Com a altura mínima original (560), a janela no Mac ficava mais
            # alta que a área útil da tela de um MacBook. A página continua
            # crescendo com a janela; só o mínimo diminui.
            self.visualizador.setMinimumSize(420, 420)
        self.visualizador.regiao_marcada.connect(self._regiao_marcada)
        col.addWidget(self.visualizador, 1)
        self.lb_marcacao = QLabel(
            "Para marcar uma assinatura ou foto, clique em 'Marcar região na página' "
            "e arraste sobre a área."
        )
        self.lb_marcacao.setWordWrap(True)
        col.addWidget(self.lb_marcacao)
        divisor.addWidget(direita)
        divisor.setSizes([780, 500])
        layout.addWidget(divisor, 1)

        # A pasta de saída só podia ser escolhida na aba 1. Quem chegava aqui
        # e clicava em processar recebia um aviso sem ter onde resolvê-lo.
        rodape = QHBoxLayout()
        self.lb_saida_revisao = QLabel()
        self.lb_saida_revisao.setWordWrap(True)
        bt_saida_revisao = QPushButton("Selecionar pasta de saída…")
        bt_saida_revisao.clicked.connect(self._selecionar_pasta)
        rodape.addWidget(self.lb_saida_revisao, 1)
        rodape.addWidget(bt_saida_revisao)
        layout.addLayout(rodape)

        self.bt_processar = QPushButton("Aplicar redação, validar e gerar relatório ▶")
        self.bt_processar.clicked.connect(self._processar)
        self.bt_processar.setEnabled(False)
        self.bt_processar.setStyleSheet(estilo_botao_principal())
        self.bt_processar.setMinimumHeight(44)
        layout.addWidget(self.bt_processar)
        return aba

    # ------------------------------------------------------------ aba 5
    def _aba_resultado(self) -> QWidget:
        aba = QWidget()
        layout = QVBoxLayout(aba)
        self.txt_resultado = QTextBrowser()
        layout.addWidget(self.txt_resultado, 1)
        botoes = QHBoxLayout()
        self.bt_abrir_pasta = QPushButton("Abrir pasta de saída")
        self.bt_abrir_pasta.clicked.connect(self._abrir_pasta)
        self.bt_abrir_pasta.setEnabled(False)
        botoes.addWidget(self.bt_abrir_pasta)
        botoes.addStretch(1)
        layout.addLayout(botoes)
        return aba

    # ------------------------------------------------------------- ações
    def _selecionar_arquivos(self) -> None:
        arquivos, _ = QFileDialog.getOpenFileNames(
            self, "Selecionar PDFs", "", "Documentos PDF (*.pdf)"
        )
        for arquivo in arquivos:
            if not self.lista_arquivos.findItems(arquivo, Qt.MatchFlag.MatchExactly):
                self.lista_arquivos.addItem(QListWidgetItem(arquivo))
        self.statusBar().showMessage(
            f"{self.lista_arquivos.count()} documento(s) selecionado(s)."
        )

    def _remover_arquivos(self) -> None:
        for item in self.lista_arquivos.selectedItems():
            self.lista_arquivos.takeItem(self.lista_arquivos.row(item))

    def _limpar_sessao(self) -> None:
        resposta = QMessageBox.question(
            self,
            "Limpar sessão",
            "Descartar documentos, ocorrências detectadas e decisões desta sessão?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        self.lista_arquivos.clear()
        self.sessao.limpar()
        self.cb_documento.clear()
        self.painel_revisao.atualizar()
        self.txt_inspecao.clear()
        self.txt_resultado.clear()
        self.bt_analisar.setEnabled(False)
        self.bt_processar.setEnabled(False)
        self.statusBar().showMessage("Sessão limpa.")

    def _selecionar_pasta(self) -> bool:
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar pasta de saída")
        if not pasta:
            return False
        self.pasta_saida = Path(pasta)
        self.cfg.pasta_saida_padrao = pasta
        self._atualizar_rotulo_saida()
        return True

    def _atualizar_rotulo_saida(self) -> None:
        """Mantém o caminho visível nas duas abas que o usam."""
        if self.pasta_saida:
            texto = f"Pasta de saída: {self.pasta_saida}"
        else:
            texto = "Pasta de saída: (não selecionada)"
        for rotulo in (
            getattr(self, "lb_saida", None),
            getattr(self, "lb_saida_revisao", None),
        ):
            if rotulo is not None:
                rotulo.setText(texto)

    def _arquivos(self) -> list[Path]:
        return [
            Path(self.lista_arquivos.item(i).text())
            for i in range(self.lista_arquivos.count())
        ]

    def _ocupado(self, ocupado: bool) -> None:
        self.bt_inspecionar.setEnabled(not ocupado)
        self.bt_analisar.setEnabled(not ocupado and bool(self.sessao.inspecoes))
        self.bt_processar.setEnabled(
            not ocupado and bool(self.sessao.gerenciador.candidatos)
        )
        self.bt_cancelar.setEnabled(ocupado)

    def _progresso(self, etapa: str, atual: int, total: int) -> None:
        self.barra.setMaximum(max(total, 1))
        self.barra.setValue(atual)
        self.statusBar().showMessage(f"{etapa}: {atual}/{total}")

    def _cancelar(self) -> None:
        self.sessao.cancelar.set()
        self.statusBar().showMessage(
            "Cancelamento solicitado: encerrando de forma controlada…"
        )

    # --------------------------------------------------------- etapa 1 → 2
    def _inspecionar(self) -> None:
        arquivos = self._arquivos()
        if not arquivos:
            QMessageBox.information(self, APP_NOME, "Selecione ao menos um PDF.")
            return
        self.sessao.reiniciar_cancelamento()
        self._ocupado(True)
        self.worker = WorkerInspecao(self.sessao, arquivos)
        self.worker.progresso.connect(self._progresso)
        self.worker.falhou.connect(self._erro)
        self.worker.concluido.connect(self._inspecao_concluida)
        self.worker.start()

    def _inspecao_concluida(self, resultados: list) -> None:
        self._ocupado(False)
        self.txt_inspecao.setHtml(self._html_inspecao(resultados))
        self.bt_analisar.setEnabled(bool(resultados))
        self.abas.setCurrentIndex(1)
        self.statusBar().showMessage("Inspeção concluída.")

    def _html_inspecao(self, resultados: list) -> str:
        cores = cores_html()
        partes = ["<h2>Inspeção estrutural</h2>"]
        for insp in resultados:
            partes.append(f"<h3>{html.escape(insp.arquivo)}</h3>")
            if insp.erro_fatal:
                partes.append(
                    f"<p style='color:{cores['erro']}'><b>Erro:</b> "
                    f"{html.escape(insp.erro_fatal)}</p>"
                )
            partes.append(
                "<ul>"
                f"<li>Páginas: {insp.total_paginas} "
                f"(texto: {insp.paginas_texto}, digitalizadas: {insp.paginas_digitalizadas}, "
                f"híbridas: {insp.paginas_hibridas}, vazias: {insp.paginas_vazias})</li>"
                f"<li>Metadados preenchidos: {', '.join(insp.metadados.keys()) or 'nenhum'}</li>"
                f"<li>Formulário interativo: {'sim' if insp.tem_formulario else 'não'}</li>"
                f"<li>Anotações: {insp.qtd_anotacoes} · Links: {insp.qtd_links}</li>"
                f"<li>Arquivos incorporados: {len(insp.arquivos_incorporados)}</li>"
                f"<li>Camadas de conteúdo: {len(insp.camadas_ocg)}</li>"
                f"<li>Assinaturas digitais: {len(insp.assinaturas)}</li>"
                f"<li>Marcadores: {insp.marcadores}</li>"
                f"<li>SHA-256 da entrada: <code>{insp.sha256_entrada[:32]}…</code></li>"
                "</ul>"
            )
            if insp.riscos:
                partes.append("<b>Riscos estruturais:</b><ul>")
                for risco in insp.riscos:
                    cor = cores["erro"] if risco.bloqueia_aprovacao else cores["alerta"]
                    marca = " (bloqueia a aprovação)" if risco.bloqueia_aprovacao else ""
                    partes.append(
                        f"<li style='color:{cor}'><b>{html.escape(risco.codigo)}</b>{marca}: "
                        f"{html.escape(risco.descricao)}</li>"
                    )
                partes.append("</ul>")
            else:
                partes.append("<p>Nenhum risco estrutural identificado nesta etapa.</p>")
        return "".join(partes)

    # --------------------------------------------------------- etapa 2 → 4
    def _analisar(self) -> None:
        arquivos = self._arquivos()
        if not arquivos:
            return
        self.sessao.reiniciar_cancelamento()
        self._ocupado(True)
        self.worker = WorkerAnalise(self.sessao, arquivos)
        self.worker.progresso.connect(self._progresso)
        self.worker.mensagem.connect(self.statusBar().showMessage)
        self.worker.falhou.connect(self._erro)
        self.worker.concluido.connect(self._analise_concluida)
        self.worker.start()

    def _analise_concluida(self, total: int) -> None:
        self._ocupado(False)
        self.cb_documento.blockSignals(True)
        self.cb_documento.clear()
        self.cb_documento.addItem("Todos os documentos", "")
        for arquivo in self._arquivos():
            self.cb_documento.addItem(arquivo.name, arquivo.name)
        self.cb_documento.blockSignals(False)
        self.painel_revisao.definir_documento("")
        self.painel_revisao.atualizar()
        self.bt_processar.setEnabled(total > 0)
        self.abas.setCurrentIndex(3)
        pendentes = len(self.sessao.gerenciador.pendentes())
        self.statusBar().showMessage(
            f"{total} ocorrência(s) detectada(s); {pendentes} aguardam decisão humana."
        )

    def _trocar_documento(self) -> None:
        self.painel_revisao.definir_documento(self.cb_documento.currentData() or "")

    def _mostrar_pagina(self, candidato) -> None:
        caminho = next(
            (a for a in self._arquivos() if a.name == candidato.documento), None
        )
        if caminho is None:
            return
        self.visualizador.carregar(
            caminho,
            candidato.pagina,
            self.sessao.gerenciador.por_documento(candidato.documento),
        )

    def _atualizar_visualizador(self) -> None:
        candidato = self.painel_revisao.candidato_atual()
        if candidato is not None:
            self._mostrar_pagina(candidato)

    def _ativar_marcacao(self) -> None:
        candidato = self.painel_revisao.candidato_atual()
        if candidato is None:
            QMessageBox.information(
                self,
                APP_NOME,
                "Selecione uma ocorrência da página desejada para exibi-la e, em "
                "seguida, arraste o mouse sobre a área a ser removida.",
            )
            return
        self.visualizador.definir_modo_marcacao(True)
        self.lb_marcacao.setText(
            "Modo de marcação ativo: arraste sobre a área a ser removida na página "
            f"{candidato.pagina + 1} de {candidato.documento}."
        )

    def _regiao_marcada(self, bbox: tuple) -> None:
        candidato = self.painel_revisao.candidato_atual()
        if candidato is None:
            return
        self.sessao.adicionar_regiao_manual(candidato.documento, candidato.pagina, bbox)
        self.visualizador.definir_modo_marcacao(False)
        self.lb_marcacao.setText("Região marcada e confirmada para redação.")
        self.painel_revisao.atualizar()
        self._atualizar_visualizador()

    # --------------------------------------------------------- etapa 4 → 5
    def _processar(self) -> None:
        if self.pasta_saida is None:
            # Avisar sem oferecer saída obriga o usuário a procurar o botão em
            # outra aba. Aqui o próprio aviso resolve.
            resposta = QMessageBox.question(
                self,
                APP_NOME,
                "Ainda não há pasta de saída escolhida.\n\n"
                "Ela precisa ser diferente da pasta dos originais: o arquivo de "
                "entrada nunca é alterado.\n\nEscolher agora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return
            if not self._selecionar_pasta():
                return
        pendentes = self.sessao.gerenciador.pendentes()
        if pendentes:
            resposta = QMessageBox.question(
                self,
                "Ocorrências pendentes",
                f"Há {len(pendentes)} ocorrência(s) sem decisão humana. Elas NÃO serão "
                "redigidas e impedirão a aprovação do documento. Deseja continuar "
                "mesmo assim?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if resposta != QMessageBox.StandardButton.Yes:
                return
        self.sessao.reiniciar_cancelamento()
        self._ocupado(True)
        self.worker = WorkerProcessamento(
            self.sessao, self.pasta_saida, self.chk_sobrescrever.isChecked()
        )
        self.worker.progresso.connect(self._progresso)
        self.worker.falhou.connect(self._erro)
        self.worker.concluido.connect(self._processamento_concluido)
        self.worker.start()

    def _processamento_concluido(self, relatorios: list) -> None:
        self._ocupado(False)
        self.txt_resultado.setHtml(self._html_resultado(relatorios))
        self.bt_abrir_pasta.setEnabled(True)
        self.painel_revisao.atualizar()
        self.abas.setCurrentIndex(4)
        self.statusBar().showMessage("Processamento concluído.")

    def _html_resultado(self, relatorios: list[RelatorioDocumento]) -> str:
        cores = cores_html()
        vereditos = cores_veredito()
        partes = ["<h2>Resultado do processamento</h2>"]
        for rel in relatorios:
            veredito = rel.veredito
            cor = vereditos.get(veredito, cores["atencao"])
            partes.append(f"<h3>{html.escape(rel.arquivo_entrada)}</h3>")
            partes.append(
                f"<p style='font-size:15px;color:{cor}'><b>"
                f"{html.escape(ROTULOS_VEREDITO.get(veredito, veredito.value))}</b></p>"
            )
            if rel.erro:
                partes.append(
                    f"<p style='color:{cores['erro']}'><b>Erro:</b> "
                    f"{html.escape(rel.erro)}</p>"
                )
            if rel.arquivo_saida:
                partes.append(
                    f"<p>Arquivo gerado: <code>{html.escape(rel.arquivo_saida)}</code></p>"
                )
            red = rel.redacao
            val = rel.validacao
            if red:
                partes.append(
                    f"<ul><li>Áreas redigidas: {red.redacoes_aplicadas} "
                    f"(texto: {red.redacoes_texto}, imagem: {red.redacoes_imagem})</li>"
                    f"<li>Metadados removidos: {', '.join(red.metadados_removidos) or 'nenhum'}</li>"
                    f"<li>Estruturas não tratadas: "
                    f"{'; '.join(red.estruturas_nao_tratadas) or 'nenhuma'}</li>"
                    f"<li>SHA-256 da saída: <code>{red.sha256_saida[:32]}…</code></li></ul>"
                )
            if val:
                partes.append(
                    f"<ul><li>Páginas reextraídas: {val.paginas_verificadas_texto} · "
                    f"reexaminadas por OCR: {val.paginas_verificadas_ocr}</li>"
                    f"<li>Ocorrências detectadas no documento de saída: {len(val.residuais)}</li>"
                    f"<li>Identificadores originais ainda recuperáveis: "
                    f"{val.residuais_conhecidos}</li>"
                    f"<li>Áreas conferidas: {val.areas_redacao_conferidas}</li></ul>"
                )
                bloqueios = [r for r in val.riscos if r.bloqueia_aprovacao]
                if bloqueios:
                    partes.append("<b>Pendências que impedem a aprovação:</b><ul>")
                    for risco in bloqueios:
                        partes.append(
                            f"<li style='color:{cores['erro']}'>"
                            f"{html.escape(risco.codigo)}: "
                            f"{html.escape(risco.descricao)}</li>"
                        )
                    partes.append("</ul>")
                avisos = [
                    r for r in val.riscos if r.severidade == Severidade.AVISO
                ]
                if avisos:
                    partes.append("<b>Avisos:</b><ul>")
                    for risco in avisos:
                        partes.append(
                            f"<li style='color:{cores['alerta']}'>"
                            f"{html.escape(risco.descricao)}</li>"
                        )
                    partes.append("</ul>")
            partes.append(
                "<p><small>Relatórios técnicos gravados ao lado do arquivo de saída "
                "(<code>…_relatorio.json</code> e <code>…_relatorio.html</code>).</small></p>"
            )
        partes.append(
            f"<div style='background:{cores['aviso_fundo']};color:{cores['aviso_texto']};"
            f"padding:8px;border-left:6px solid {cores['aviso_borda']}'>"
            f"{html.escape(AVISO_PRINCIPAL)}</div>"
        )
        return "".join(partes)

    def _abrir_pasta(self) -> None:
        if self.pasta_saida:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.pasta_saida)))

    # ------------------------------------------------------------ auxiliares
    def _erro(self, mensagem: str) -> None:
        self._ocupado(False)
        QMessageBox.critical(self, APP_NOME, mensagem)
        self.statusBar().showMessage("Operação interrompida por erro.")

    def _atualizar_estado_ocr(self) -> None:
        descricao = descrever_ambiente_ocr(self.cfg.ocr)
        status = verificar_ocr(self.cfg.ocr)
        cores = cores_html()
        cor = cores["ok"] if status.disponivel else cores["erro"]
        self.lb_ocr.setText(f"<span style='color:{cor}'>OCR local: {html.escape(descricao)}</span>")

    def _verificar_ocr(self) -> None:
        self._atualizar_estado_ocr()
        QMessageBox.information(
            self, "OCR local", descrever_ambiente_ocr(self.cfg.ocr)
        )

    def _salvar_config(self) -> None:
        destino = self.cfg.salvar()
        QMessageBox.information(
            self, APP_NOME, f"Configuração gravada em:\n{destino}"
        )

    def _mostrar_limitacoes(self) -> None:
        QMessageBox.information(
            self,
            "Limitações e riscos",
            f"{AVISO_PRINCIPAL}\n\n"
            "• O OCR pode falhar em documentos de baixa qualidade; páginas sem "
            "cobertura adequada impedem a aprovação.\n"
            "• A detecção de nomes é heurística e pode gerar falsos positivos e "
            "falsos negativos.\n"
            "• A reidentificação por contexto (datas, narrativa, relações) não é "
            "tratada pela ferramenta.\n"
            f"• {AVISO_ASSINATURA}\n"
            f"• {AVISO_SSD}",
        )

    def _mostrar_sobre(self) -> None:
        QMessageBox.about(
            self,
            f"Sobre o {APP_NOME}",
            f"<b>{APP_NOME}</b> versão {APP_VERSAO}<br><br>"
            "Processamento integralmente local. O aplicativo não envia documentos, "
            "textos, imagens ou metadados para serviços externos, e bloqueia o acesso "
            "à rede durante o processamento.<br><br>"
            f"<i>{html.escape(AVISO_PRINCIPAL)}</i>",
        )

    def closeEvent(self, evento) -> None:  # noqa: N802
        if self.worker is not None and self.worker.isRunning():
            self.sessao.cancelar.set()
            self.worker.wait(5000)
        self.sessao.limpar()
        super().closeEvent(evento)
