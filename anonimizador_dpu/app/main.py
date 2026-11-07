"""Ponto de entrada do Anonimizador DPU.

Execução:

    python -m anonimizador_dpu.app.main

O aplicativo funciona com privilégios normais de usuário. Não exige
administrador, não altera configurações do sistema e não acessa a rede.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from ..core.audit_logger import configurar_log
from ..core.config import APP_NOME, APP_VERSAO, Config
from ..core.ocr_engine import verificar_ocr


def main(argv: list[str] | None = None) -> int:
    argumentos = list(argv if argv is not None else sys.argv)
    cfg = Config.carregar()
    configurar_log(cfg.nivel_log)

    app = QApplication(argumentos)
    app.setApplicationName(APP_NOME)
    app.setApplicationVersion(APP_VERSAO)
    app.setOrganizationName("Defensoria Pública da União")

    from .ui.main_window import JanelaPrincipal  # import tardio: acelera a abertura
    from .ui.tema import estilo_aplicacao

    app.setStyleSheet(estilo_aplicacao())

    janela = JanelaPrincipal(cfg)
    janela.show()

    status = verificar_ocr(cfg.ocr)
    if not status.disponivel:
        QMessageBox.warning(
            janela,
            "OCR local indisponível",
            "O OCR local não está disponível:\n\n"
            f"{status.erro}\n\n"
            "Páginas digitalizadas não poderão ser examinadas e o documento não "
            "poderá ser aprovado nos testes automatizados. Instale o Tesseract OCR "
            "com o idioma português (por.traineddata) e reabra o aplicativo.\n\n"
            "Nenhum componente é baixado automaticamente: a instalação é uma "
            "operação separada do processamento de documentos.",
        )

    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
