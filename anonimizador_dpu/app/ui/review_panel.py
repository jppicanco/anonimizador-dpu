"""Tela de revisão humana das ocorrências detectadas.

A tabela distingue claramente os estados previstos: detectado, confirmado para
redação, rejeitado, pendente, redigido, verificado e falha crítica.

Minimização de dados: por padrão a coluna de valor mostra apenas uma forma
mascarada, e o trecho contextual vem com o dado substituído pela categoria. O
usuário pode habilitar a exibição integral quando precisar decidir sobre uma
ocorrência — a decisão é dele, e a interface registra que isso é necessário
apenas em caso de dúvida.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.candidate_manager import GerenciadorCandidatos
from ...core.config import Config
from ...core.models import (
    CATEGORIAS_INFO,
    ROTULOS_STATUS,
    Candidato,
    Categoria,
    Status,
    rotulo_categoria,
)
from .tema import (
    ROTULOS_CONFIANCA,
    cores_confianca,
    faixa_confianca,
    fundo_neutro,
    fundos_status,
    texto_sobre,
)

#: As cores dependem do tema ativo e são resolvidas em ``tema.py``.

#: Coluna da caixa de marcação. Marcada = será removida do documento.
COLUNA_REMOVER = 0

COLUNAS = [
    "Remover",
    "Documento",
    "Pág.",
    "Categoria",
    "Origem",
    "Confiança",
    "Situação",
    "Pseudônimo",
    "Valor",
    "Trecho (minimizado)",
    "Áreas",
    "Observação",
]

COLUNA_CONFIANCA = COLUNAS.index("Confiança")
COLUNA_AREAS = COLUNAS.index("Áreas")


class PainelRevisao(QWidget):
    """Lista de candidatos com as ações de revisão."""

    ocorrencia_selecionada = Signal(object)  # Candidato
    marcar_regiao_solicitada = Signal()
    alteracoes = Signal()

    def __init__(
        self,
        gerenciador: GerenciadorCandidatos,
        cfg: Config | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.gerenciador = gerenciador
        self.cfg = cfg or Config()
        self._exibir_valores = False
        self._filtro_documento = ""
        #: Enquanto a tabela é repovoada, os sinais de marcação são ignorados.
        self._povoando = False
        self._montar()

    # ------------------------------------------------------------- construção
    def _montar(self) -> None:
        layout = QVBoxLayout(self)

        explicacao = QLabel(
            "Tudo que foi detectado já está <b>marcado para remoção</b>. "
            "Desmarque a caixa da esquerda para manter uma ocorrência no texto. "
            "A cor da coluna <b>Confiança</b> indica o que merece um olhar: "
            "laranja é detecção menos segura."
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)

        filtros = QHBoxLayout()
        filtros.addWidget(QLabel("Filtrar:"))
        self.cb_status = QComboBox()
        self.cb_status.addItem("Todas as situações", "")
        for status, rotulo in ROTULOS_STATUS.items():
            self.cb_status.addItem(rotulo, status.value)
        self.cb_status.currentIndexChanged.connect(self.atualizar)
        filtros.addWidget(self.cb_status)

        self.cb_categoria = QComboBox()
        self.cb_categoria.addItem("Todas as categorias", "")
        for categoria, (rotulo, _, _) in CATEGORIAS_INFO.items():
            self.cb_categoria.addItem(rotulo, categoria.value)
        self.cb_categoria.currentIndexChanged.connect(self.atualizar)
        filtros.addWidget(self.cb_categoria)

        self.ed_busca = QLineEdit()
        self.ed_busca.setPlaceholderText("Documento ou pseudônimo…")
        self.ed_busca.textChanged.connect(self.atualizar)
        if sys.platform == "darwin":
            # Com a fonte maior do Mac, os filtros vizinhos espremiam o campo
            # de busca até ele virar um quadradinho com reticências.
            self.ed_busca.setMinimumWidth(150)
        filtros.addWidget(self.ed_busca, 1)

        self.chk_valores = QCheckBox("Exibir valores originais (apenas para decidir)")
        self.chk_valores.toggled.connect(self._alternar_valores)
        filtros.addWidget(self.chk_valores)
        layout.addLayout(filtros)

        self.tabela = QTableWidget(0, len(COLUNAS))
        self.tabela.setHorizontalHeaderLabels(COLUNAS)
        self.tabela.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabela.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.itemSelectionChanged.connect(self._emitir_selecao)
        self.tabela.itemChanged.connect(self._marcacao_alterada)
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        cabecalho.setStretchLastSection(True)
        layout.addWidget(self.tabela, 1)

        acoes = QGroupBox("Decisões")
        self.bt_confirmar = QPushButton("Marcar selecionadas para remoção")
        self.bt_confirmar.clicked.connect(lambda: self._definir(Status.CONFIRMADO))
        self.bt_rejeitar = QPushButton("Desmarcar selecionadas (manter no texto)")
        self.bt_rejeitar.clicked.connect(lambda: self._definir(Status.REJEITADO))
        self.bt_equivalentes = QPushButton("Aplicar a equivalentes…")
        self.bt_equivalentes.clicked.connect(self._aplicar_equivalentes)
        self.bt_categoria = QPushButton("Alterar categoria…")
        self.bt_categoria.clicked.connect(self._alterar_categoria)
        self.bt_separar = QPushButton("Separar pessoa homônima…")
        self.bt_separar.clicked.connect(self._separar)
        self.bt_regiao = QPushButton("Marcar região na página")
        self.bt_regiao.clicked.connect(self.marcar_regiao_solicitada.emit)
        botoes = (
            self.bt_confirmar,
            self.bt_rejeitar,
            self.bt_equivalentes,
            self.bt_categoria,
            self.bt_separar,
            self.bt_regiao,
        )
        if sys.platform == "darwin":
            # A fonte do sistema no Mac é maior que a do Windows: numa fileira
            # só, os seis botões deixavam a janela mais larga que a tela de um
            # MacBook Air. Em duas fileiras de três, cabem.
            grade = QGridLayout(acoes)
            for indice, bt in enumerate(botoes):
                grade.addWidget(bt, indice // 3, indice % 3)
        else:
            linha = QHBoxLayout(acoes)
            for bt in botoes:
                linha.addWidget(bt)
        layout.addWidget(acoes)

        self.lb_resumo = QLabel()
        self.lb_resumo.setWordWrap(True)
        layout.addWidget(self.lb_resumo)

    # ----------------------------------------------------------------- dados
    def definir_documento(self, nome: str) -> None:
        self._filtro_documento = nome
        self.atualizar()

    def _candidatos_filtrados(self) -> list[Candidato]:
        status = self.cb_status.currentData() or ""
        categoria = self.cb_categoria.currentData() or ""
        busca = self.ed_busca.text().strip().lower()
        saida = []
        for c in self.gerenciador.candidatos:
            if self._filtro_documento and c.documento != self._filtro_documento:
                continue
            if status and c.status.value != status:
                continue
            if categoria and c.categoria.value != categoria:
                continue
            if busca and busca not in (c.documento + (c.pseudonimo or "")).lower():
                continue
            saida.append(c)
        return saida

    def atualizar(self) -> None:
        candidatos = self._candidatos_filtrados()
        self._povoando = True
        self.tabela.setRowCount(len(candidatos))
        fundos = fundos_status()
        neutro = fundo_neutro()
        for linha, c in enumerate(candidatos):
            self._preencher_linha(linha, c, fundos, neutro)
        self.tabela.resizeColumnsToContents()
        self._povoando = False
        self._atualizar_resumo()

    def _preencher_linha(
        self,
        linha: int,
        c: Candidato,
        fundos: dict[Status, QColor],
        neutro: QColor,
    ) -> None:
        valores = [
            "",  # coluna da caixa de marcação
            c.documento,
            str(c.pagina + 1),
            rotulo_categoria(c.categoria),
            c.origem.value,
            f"{c.confianca:.0%}",
            ROTULOS_STATUS.get(c.status, c.status.value),
            c.pseudonimo or "",
            c.valor if self._exibir_valores else c.valor_mascarado(),
            c.contexto if self._exibir_valores else c.contexto[:60],
            str(len(c.bboxes)) if c.bboxes else "sem área",
            c.falha or c.motivo,
        ]
        fundo = fundos.get(c.status, neutro)
        # O texto precisa ser definido junto com o fundo: sem isso, ele é
        # herdado da paleta do sistema e some sobre a cor da situação.
        frente = texto_sobre(fundo)
        for coluna, valor in enumerate(valores):
            item = QTableWidgetItem(valor)
            item.setBackground(QBrush(fundo))
            item.setForeground(QBrush(frente))
            item.setData(Qt.ItemDataRole.UserRole, c.id)
            if coluna == COLUNA_REMOVER:
                self._preparar_caixa(item, c)
            if coluna == COLUNA_CONFIANCA:
                self._destacar_confianca(item, c)
            if c.bbox_incerta and coluna == COLUNA_AREAS:
                item.setToolTip(
                    "Área não determinada com segurança: a redação não será aplicada "
                    "e a página ficará pendente."
                )
            self.tabela.setItem(linha, coluna, item)

    def _marcacao_alterada(self, item: QTableWidgetItem) -> None:
        """Desmarcar significa 'não remover'; marcar de volta, 'remover'."""
        if self._povoando or item.column() != COLUNA_REMOVER:
            return
        identificador = item.data(Qt.ItemDataRole.UserRole)
        if not identificador:
            return
        marcado = item.checkState() == Qt.CheckState.Checked
        self.gerenciador.definir_status(
            str(identificador), Status.CONFIRMADO if marcado else Status.REJEITADO
        )
        candidato = self.gerenciador.obter(str(identificador))
        if candidato is not None:
            # Só a linha tocada é repintada: reconstruir a tabela inteira
            # faria a lista saltar a cada clique.
            self._povoando = True
            self._preencher_linha(item.row(), candidato, fundos_status(), fundo_neutro())
            self._povoando = False
        self._atualizar_resumo()
        self.alteracoes.emit()

    def _preparar_caixa(self, item: QTableWidgetItem, candidato: Candidato) -> None:
        """Caixa de marcação: marcada significa que a ocorrência será removida."""
        item.setFlags(
            (item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            & ~Qt.ItemFlag.ItemIsEditable
        )
        marcado = candidato.status not in (Status.REJEITADO,)
        item.setCheckState(
            Qt.CheckState.Checked if marcado else Qt.CheckState.Unchecked
        )
        if candidato.status in (Status.REDIGIDO, Status.VERIFICADO):
            # Já aplicada: a marcação não pode mais ser desfeita neste arquivo.
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsUserCheckable)
            item.setToolTip("Já removida do arquivo de saída.")
        else:
            item.setToolTip(
                "Marcada: será removida do documento.\n"
                "Desmarque para manter esta ocorrência no texto."
            )

    def _destacar_confianca(self, item: QTableWidgetItem, candidato: Candidato) -> None:
        """Sinaliza o grau de certeza da detecção.

        Como tudo entra marcado para remoção, a cor da linha deixou de separar
        o certo do duvidoso. É a confiança que passa a orientar o revisor sobre
        o que merece um olhar antes de desmarcar — ou de deixar sair.
        """
        faixa = faixa_confianca(candidato.confianca, self.cfg)
        fundo = cores_confianca()[faixa]
        item.setBackground(QBrush(fundo))
        item.setForeground(QBrush(texto_sobre(fundo)))
        item.setToolTip(ROTULOS_CONFIANCA[faixa])

    def _atualizar_resumo(self) -> None:
        documento = self._filtro_documento or None
        r = self.gerenciador.resumo(documento)
        self.lb_resumo.setText(
            f"Total: {r['total']} | Confirmadas: {r['confirmados']} | "
            f"Rejeitadas: {r['rejeitados']} | Pendentes: {r['pendentes']} | "
            f"Redigidas: {r['redigidos']} | Verificadas: {r['verificados']} | "
            f"Falhas críticas: {r['falhas']} | Entidades distintas: {r['entidades']}"
        )

    # ----------------------------------------------------------------- ações
    def _ids_selecionados(self) -> list[str]:
        ids: list[str] = []
        for indice in self.tabela.selectionModel().selectedRows():
            item = self.tabela.item(indice.row(), 0)
            if item is not None:
                identificador = item.data(Qt.ItemDataRole.UserRole)
                if identificador:
                    ids.append(str(identificador))
        return ids

    def candidato_atual(self) -> Candidato | None:
        ids = self._ids_selecionados()
        return self.gerenciador.obter(ids[0]) if ids else None

    def _emitir_selecao(self) -> None:
        candidato = self.candidato_atual()
        if candidato is not None:
            self.ocorrencia_selecionada.emit(candidato)

    def _definir(self, status: Status) -> None:
        ids = self._ids_selecionados()
        if not ids:
            QMessageBox.information(self, "Revisão", "Selecione ao menos uma ocorrência.")
            return
        for identificador in ids:
            self.gerenciador.definir_status(identificador, status)
        self.atualizar()
        self.alteracoes.emit()

    def _aplicar_equivalentes(self) -> None:
        candidato = self.candidato_atual()
        if candidato is None:
            QMessageBox.information(self, "Revisão", "Selecione uma ocorrência.")
            return
        equivalentes = self.gerenciador.equivalentes(candidato.id)
        resposta = QMessageBox.question(
            self,
            "Aplicar a ocorrências equivalentes",
            f"Aplicar a situação '{ROTULOS_STATUS.get(candidato.status, '')}' a "
            f"{len(equivalentes)} ocorrência(s) da mesma entidade "
            f"({candidato.pseudonimo})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if resposta != QMessageBox.StandardButton.Yes:
            return
        alterados = self.gerenciador.aplicar_em_equivalentes(candidato.id, candidato.status)
        self.atualizar()
        self.alteracoes.emit()
        QMessageBox.information(
            self, "Revisão", f"{alterados} ocorrência(s) atualizada(s)."
        )

    def _alterar_categoria(self) -> None:
        candidato = self.candidato_atual()
        if candidato is None:
            return
        opcoes = [rotulo_categoria(c) for c in CATEGORIAS_INFO]
        atual = opcoes.index(rotulo_categoria(candidato.categoria))
        escolha, ok = QInputDialog.getItem(
            self, "Alterar categoria", "Nova categoria:", opcoes, atual, False
        )
        if not ok:
            return
        for categoria in CATEGORIAS_INFO:
            if rotulo_categoria(categoria) == escolha:
                self.gerenciador.definir_categoria(candidato.id, categoria)
                break
        self.atualizar()
        self.alteracoes.emit()

    def _separar(self) -> None:
        candidato = self.candidato_atual()
        if candidato is None:
            return
        rotulo, ok = QInputDialog.getText(
            self,
            "Separar pessoa homônima",
            "Identificação interna para esta pessoa (não aparece no documento):",
        )
        if not ok:
            return
        novo = self.gerenciador.separar_entidade(candidato.id, rotulo)
        self.atualizar()
        self.alteracoes.emit()
        if novo:
            QMessageBox.information(
                self, "Revisão", f"Esta ocorrência passou a usar o pseudônimo {novo}."
            )

    def _alternar_valores(self, ativo: bool) -> None:
        if ativo:
            resposta = QMessageBox.warning(
                self,
                "Exibição de dados pessoais",
                "Os valores originais serão exibidos na tela para permitir a decisão "
                "sobre cada ocorrência. Confirme que o ambiente é adequado.",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            )
            if resposta != QMessageBox.StandardButton.Ok:
                self.chk_valores.setChecked(False)
                return
        self._exibir_valores = ativo
        self.atualizar()
