"""Visualizador de página com destaque das áreas e marcação manual de região.

O visualizador renderiza a página com o PyMuPDF e desenha por cima as áreas das
ocorrências, com cores conforme o status. O usuário pode arrastar o mouse para
marcar uma região retangular a ser redigida — útil para assinaturas, carimbos e
fotografias, que não são alcançados por detecção textual.
"""

from __future__ import annotations

from pathlib import Path

import fitz
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy

from ...core.models import Candidato, Status

CORES_STATUS = {
    Status.DETECTADO: QColor(230, 150, 20, 90),
    Status.CONFIRMADO: QColor(200, 30, 30, 110),
    Status.REJEITADO: QColor(120, 120, 120, 70),
    Status.PENDENTE: QColor(240, 180, 0, 110),
    Status.REDIGIDO: QColor(20, 110, 60, 120),
    Status.VERIFICADO: QColor(20, 110, 60, 120),
    Status.FALHA_CRITICA: QColor(150, 0, 150, 140),
}


class VisualizadorPagina(QLabel):
    """Exibe uma página do PDF e permite marcar regiões manualmente."""

    regiao_marcada = Signal(tuple)  # (x0, y0, x1, y1) em pontos da página

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(420, 560)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("background: #3a3a3a;")
        self.setText("Nenhuma página carregada.")

        self._pixmap: QPixmap | None = None
        self._escala = 1.0
        self._origem = (0.0, 0.0)
        self._areas: list[tuple[tuple[float, float, float, float], Status]] = []
        self._selecao_inicio: QPoint | None = None
        self._selecao_atual: QRect | None = None
        self._modo_marcacao = False
        self._deslocamento = QPoint(0, 0)

    # ----------------------------------------------------------- carregamento
    def carregar(
        self,
        caminho: Path,
        numero_pagina: int,
        candidatos: list[Candidato] | None = None,
        dpi: int = 110,
    ) -> bool:
        """Renderiza a página indicada e registra as áreas a destacar."""
        try:
            doc = fitz.open(caminho)
        except Exception:
            self.setText("Não foi possível abrir o documento para visualização.")
            return False
        with doc:
            if numero_pagina >= doc.page_count:
                self.setText("Página inexistente.")
                return False
            page = doc[numero_pagina]
            zoom = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
            imagem = QImage(
                pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888
            )
            self._pixmap = QPixmap.fromImage(imagem.copy())
            self._escala = zoom
            self._origem = (page.rect.x0, page.rect.y0)

        self._areas = [
            (bbox, c.status)
            for c in (candidatos or [])
            if c.pagina == numero_pagina
            for bbox in c.bboxes
        ]
        self.setText("")
        self.update()
        return True

    def definir_modo_marcacao(self, ativo: bool) -> None:
        self._modo_marcacao = ativo
        self.setCursor(
            Qt.CursorShape.CrossCursor if ativo else Qt.CursorShape.ArrowCursor
        )

    # ---------------------------------------------------------------- desenho
    def paintEvent(self, evento) -> None:  # noqa: N802 - API do Qt
        super().paintEvent(evento)
        if self._pixmap is None:
            return
        painter = QPainter(self)
        destino = self._retangulo_destino()
        painter.drawPixmap(destino, self._pixmap)

        fator = destino.width() / max(self._pixmap.width(), 1)
        for bbox, status in self._areas:
            x0, y0, x1, y1 = bbox
            rx = destino.x() + (x0 - self._origem[0]) * self._escala * fator
            ry = destino.y() + (y0 - self._origem[1]) * self._escala * fator
            rw = (x1 - x0) * self._escala * fator
            rh = (y1 - y0) * self._escala * fator
            cor = CORES_STATUS.get(status, QColor(200, 200, 0, 90))
            painter.fillRect(QRect(int(rx), int(ry), int(rw), int(rh)), cor)
            painter.setPen(QPen(cor.darker(160), 1))
            painter.drawRect(QRect(int(rx), int(ry), int(rw), int(rh)))

        if self._selecao_atual is not None:
            painter.setPen(QPen(QColor(0, 90, 200), 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._selecao_atual)
        painter.end()

    def _retangulo_destino(self) -> QRect:
        if self._pixmap is None:
            return QRect()
        disponivel = self.contentsRect()
        escala = min(
            disponivel.width() / max(self._pixmap.width(), 1),
            disponivel.height() / max(self._pixmap.height(), 1),
            1.0,
        )
        largura = int(self._pixmap.width() * escala)
        altura = int(self._pixmap.height() * escala)
        x = disponivel.x() + (disponivel.width() - largura) // 2
        y = disponivel.y() + (disponivel.height() - altura) // 2
        return QRect(x, y, largura, altura)

    # ------------------------------------------------------------------ mouse
    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if not self._modo_marcacao or self._pixmap is None:
            return
        self._selecao_inicio = evento.position().toPoint()
        self._selecao_atual = QRect(self._selecao_inicio, self._selecao_inicio)
        self.update()

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if self._selecao_inicio is None:
            return
        self._selecao_atual = QRect(
            self._selecao_inicio, evento.position().toPoint()
        ).normalized()
        self.update()

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        if self._selecao_inicio is None or self._selecao_atual is None:
            return
        destino = self._retangulo_destino()
        fator = destino.width() / max(self._pixmap.width(), 1) if self._pixmap else 1.0
        sel = self._selecao_atual.intersected(destino)
        self._selecao_inicio = None
        self._selecao_atual = None
        self.update()
        if sel.width() < 4 or sel.height() < 4:
            return
        x0 = self._origem[0] + (sel.x() - destino.x()) / (self._escala * fator)
        y0 = self._origem[1] + (sel.y() - destino.y()) / (self._escala * fator)
        x1 = self._origem[0] + (sel.right() - destino.x()) / (self._escala * fator)
        y1 = self._origem[1] + (sel.bottom() - destino.y()) / (self._escala * fator)
        self.regiao_marcada.emit((x0, y0, x1, y1))
