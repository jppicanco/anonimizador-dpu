"""Ponto de entrada do aplicativo de Mac (``Anonimizador DPU.app``).

Equivale ao ``scripts/executavel.py`` do Windows, com uma opção a mais. Rodado
no Terminal com ``--verificar``::

    "/Applications/Anonimizador DPU.app/Contents/MacOS/AnonimizadorDPU" --verificar

faz, dentro do próprio aplicativo empacotado, o que no Windows se faz com
``scripts/verificar_ambiente.py`` a partir do código-fonte: confere o OCR
embutido e o bloqueio de rede e processa, de ponta a ponta, dois PDFs
sintéticos (um com texto selecionável e um digitalizado), sem abrir janela e
sem tocar em documento real. Tudo acontece em pasta temporária, apagada ao
final.
"""

from __future__ import annotations

import os
import platform
import sys
import tempfile
from pathlib import Path

# Em execução a partir do código-fonte, garante que a raiz do projeto esteja no
# caminho de importação. No aplicativo empacotado, o pacote já está embutido.
_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

# Dados deliberadamente fictícios, os mesmos das fixtures de teste do projeto.
_NOME = "Pessoa Teste Alfa"
_CPF = "529.982.247-25"
_CEP = "70040-010"
_ENDERECO = "Rua das Flores, 123, Bairro Centro"
_TELEFONE = "(61) 99999-1234"
_PROCESSO = "0000001-78.2020.8.26.0100"

_FONTES_MAC = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
)


def _pdf_texto(destino: Path) -> None:
    import fitz

    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    linhas = [
        "EXCELENTISSIMO SENHOR JUIZ FEDERAL",
        f"Processo n. {_PROCESSO}",
        "",
        f"Requerente: {_NOME}, brasileira, nascida em 12/03/1980,",
        f"inscrita no CPF sob o n. {_CPF},",
        f"residente na {_ENDERECO}, CEP {_CEP},",
        f"telefone {_TELEFONE}.",
    ]
    for i, linha in enumerate(linhas):
        pagina.insert_text((60, 80 + i * 17), linha, fontsize=11, fontname="helv")
    doc.save(destino)
    doc.close()


def _pdf_digitalizado(destino: Path) -> None:
    import io

    import fitz
    from PIL import Image, ImageDraw, ImageFont

    fonte = None
    for caminho in _FONTES_MAC:
        if Path(caminho).exists():
            fonte = ImageFont.truetype(caminho, 38)
            break
    if fonte is None:
        fonte = ImageFont.load_default(size=38)
    imagem = Image.new("RGB", (1240, 1754), "white")
    desenho = ImageDraw.Draw(imagem)
    linhas = [
        "DECLARACAO DE RESIDENCIA",
        "",
        f"Nome: {_NOME}",
        f"CPF: {_CPF}",
        f"Endereco: {_ENDERECO}",
        f"CEP: {_CEP}",
    ]
    for i, linha in enumerate(linhas):
        desenho.text((90, 90 + i * 64), linha, fill="black", font=fonte)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")

    doc = fitz.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_image(pagina.rect, stream=buffer.getvalue())
    doc.save(destino)
    doc.close()


def _verificar() -> int:
    from anonimizador_dpu.core.audit_logger import configurar_log

    configurar_log("WARNING")

    import socket

    import fitz
    import PIL
    import PySide6

    from anonimizador_dpu.core.config import APP_NOME, APP_VERSAO, Config
    from anonimizador_dpu.core.models import ROTULOS_VEREDITO, Status, Veredito
    from anonimizador_dpu.core.ocr_engine import verificar_ocr
    from anonimizador_dpu.core.pipeline import Sessao
    from anonimizador_dpu.core.security import AcessoRedeBloqueado, rede_bloqueada

    falhas: list[str] = []

    def marcar(ok: bool, texto: str) -> None:
        print(("[ OK ]  " if ok else "[FALHA] ") + texto)
        if not ok:
            falhas.append(texto)

    print(f"{APP_NOME} {APP_VERSAO} — verificação do aplicativo")
    print("=" * 64)
    print(
        f"macOS {platform.mac_ver()[0]} ({platform.machine()}) · "
        f"Python {sys.version.split()[0]} · PyMuPDF {fitz.VersionBind} · "
        f"Pillow {PIL.__version__} · PySide6 {PySide6.__version__}"
    )
    print("-" * 64)

    # Configuração padrão, sem ler a do usuário: a verificação deve medir o
    # aplicativo como ele é distribuído.
    cfg = Config()

    status = verificar_ocr(cfg.ocr)
    if status.disponivel:
        marcar(
            True,
            f"OCR: Tesseract {status.versao} — idiomas: {', '.join(sorted(status.idiomas))}",
        )
    else:
        marcar(False, f"OCR indisponível: {status.erro}")
    if getattr(sys, "frozen", False):
        pacote = Path(sys.executable).resolve().parents[2]  # …/Anonimizador DPU.app
        embutido = bool(status.caminho) and str(Path(status.caminho).resolve()).startswith(
            str(pacote)
        )
        marcar(embutido, f"Tesseract embutido no aplicativo: {status.caminho or '(nenhum)'}")

    # 192.0.2.1 pertence a uma faixa reservada para documentação (RFC 5737):
    # mesmo que o bloqueio falhasse, a tentativa não alcançaria ninguém.
    try:
        with rede_bloqueada():
            socket.create_connection(("192.0.2.1", 9), timeout=1)
        marcar(False, "Bloqueio de rede: a tentativa de conexão NÃO foi bloqueada")
    except AcessoRedeBloqueado:
        marcar(True, "Bloqueio de rede durante o processamento: ativo")
    except OSError as exc:
        marcar(False, f"Bloqueio de rede: erro inesperado ({exc})")

    with tempfile.TemporaryDirectory(prefix="anonimizador_verificacao_") as pasta:
        pasta = Path(pasta)
        texto = pasta / "verificacao_texto.pdf"
        digitalizado = pasta / "verificacao_digitalizado.pdf"
        _pdf_texto(texto)
        _pdf_digitalizado(digitalizado)

        sessao = Sessao(cfg)
        sessao.inspecionar([texto, digitalizado])
        for arquivo in (texto, digitalizado):
            sessao.analisar(arquivo)
        # Simula a revisão humana aceitando tudo o que foi detectado.
        for candidato in sessao.gerenciador.candidatos:
            if candidato.status in (Status.DETECTADO, Status.PENDENTE):
                candidato.status = Status.CONFIRMADO
                candidato.requer_revisao = False
        relatorios = sessao.processar_lote(pasta / "saida")

        for relatorio in relatorios:
            validacao = relatorio.validacao
            residuais = validacao.residuais_conhecidos if validacao else None
            ok = relatorio.veredito == Veredito.APROVADO_TESTES and residuais == 0
            if relatorio.arquivo_entrada == digitalizado.name:
                ok = ok and relatorio.paginas_por_ocr == 1
            rotulo = ROTULOS_VEREDITO.get(relatorio.veredito, relatorio.veredito.value)
            marcar(
                ok,
                f"{relatorio.arquivo_entrada}: {rotulo} — páginas lidas por OCR: "
                f"{relatorio.paginas_por_ocr}; identificadores ainda recuperáveis: {residuais}",
            )
            if relatorio.arquivo_saida:
                with fitz.open(relatorio.arquivo_saida) as doc:
                    conteudo = "".join(p.get_text() for p in doc)
                sobrou = [v for v in (_NOME, _CPF) if v in conteudo]
                marcar(
                    not sobrou,
                    "Dados fictícios removidos do arquivo gerado"
                    if not sobrou
                    else f"Ainda presentes no arquivo gerado: {', '.join(sobrou)}",
                )
        sessao.limpar()

    print("-" * 64)
    if falhas:
        print(f"{len(falhas)} problema(s) encontrado(s).")
        return 1
    print("Aplicativo pronto para uso.")
    print(
        "Lembre-se: a aprovação automatizada não garante anonimização integral "
        "e não substitui a revisão humana."
    )
    return 0


def _preparar_captura(pasta: Path) -> None:
    """Uso interno: grava imagens das abas da janela e encerra.

    Serve para conferir a aparência do aplicativo empacotado sem precisar de
    permissão de gravação de tela. Só age com a variável de ambiente
    ``ANONIMIZADOR_CAPTURA`` definida.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox

    from anonimizador_dpu.app.ui import main_window

    pasta.mkdir(parents=True, exist_ok=True)
    mostrar_original = main_window.JanelaPrincipal.show

    def capturar(janela) -> None:
        app = QApplication.instance()
        for i in range(janela.abas.count()):
            janela.abas.setCurrentIndex(i)
            app.processEvents()
            janela.grab().save(str(pasta / f"aba{i + 1}.png"))
        caixa = QMessageBox(
            QMessageBox.Icon.Question,
            "Limpar sessão",
            "Descartar documentos, ocorrências detectadas e decisões desta sessão?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            janela,
        )
        caixa.show()
        app.processEvents()
        caixa.grab().save(str(pasta / "caixa.png"))
        caixa.close()
        (pasta / "estado.txt").write_text(
            f"estilo={app.style().objectName() or type(app.style()).__name__}\n"
            f"lb_ocr={janela.lb_ocr.text()}\n",
            encoding="utf-8",
        )
        janela.close()

    def mostrar_e_capturar(self) -> None:
        mostrar_original(self)
        QTimer.singleShot(1500, lambda: capturar(self))

    main_window.JanelaPrincipal.show = mostrar_e_capturar


if __name__ == "__main__":
    if "--verificar" in sys.argv[1:]:
        raise SystemExit(_verificar())
    if os.environ.get("ANONIMIZADOR_CAPTURA"):
        _preparar_captura(Path(os.environ["ANONIMIZADOR_CAPTURA"]))

    from anonimizador_dpu.app.main import main

    raise SystemExit(main())
