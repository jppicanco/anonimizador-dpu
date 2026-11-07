"""Execução em segundo plano das etapas longas.

Todo processamento de documentos ocorre fora da thread da interface, para que a
janela não congele e o usuário possa cancelar a operação a qualquer momento. O
cancelamento é cooperativo: a sessão verifica o sinalizador entre páginas e
encerra de forma controlada, sem corromper o documento original.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from ...core.config import Config
from ...core.models import Inspecao, RelatorioDocumento
from ...core.pipeline import Sessao


class WorkerBase(QThread):
    """Base com sinais comuns a todas as tarefas em segundo plano."""

    progresso = Signal(str, int, int)  # etapa, atual, total
    mensagem = Signal(str)
    falhou = Signal(str)

    def __init__(self, sessao: Sessao, parent=None) -> None:
        super().__init__(parent)
        self.sessao = sessao

    def _emitir(self, etapa: str, atual: int, total: int) -> None:
        self.progresso.emit(etapa, atual, total)


class WorkerInspecao(WorkerBase):
    """Executa a inspeção estrutural dos documentos selecionados."""

    concluido = Signal(list)

    def __init__(self, sessao: Sessao, arquivos: list[Path], parent=None) -> None:
        super().__init__(sessao, parent)
        self.arquivos = arquivos

    def run(self) -> None:  # noqa: D102
        try:
            resultados: list[Inspecao] = self.sessao.inspecionar(
                self.arquivos, progresso=self._emitir
            )
            self.concluido.emit(resultados)
        except Exception as exc:  # pragma: no cover - proteção da thread
            self.falhou.emit(f"Falha na inspeção: {exc}")


class WorkerAnalise(WorkerBase):
    """Extrai texto, executa OCR local e detecta dados pessoais."""

    concluido = Signal(int)

    def __init__(self, sessao: Sessao, arquivos: list[Path], parent=None) -> None:
        super().__init__(sessao, parent)
        self.arquivos = arquivos

    def run(self) -> None:  # noqa: D102
        try:
            total_docs = len(self.arquivos)
            for indice, arquivo in enumerate(self.arquivos, start=1):
                if self.sessao.cancelar.is_set():
                    self.mensagem.emit("Análise cancelada pelo usuário.")
                    break
                self.mensagem.emit(
                    f"Analisando documento {indice} de {total_docs}: {Path(arquivo).name}"
                )
                self.sessao.analisar(arquivo, progresso=self._emitir)
            self.concluido.emit(len(self.sessao.gerenciador.candidatos))
        except Exception as exc:  # pragma: no cover
            self.falhou.emit(f"Falha na análise: {exc}")


class WorkerProcessamento(WorkerBase):
    """Aplica a redação, valida a saída e gera os relatórios."""

    concluido = Signal(list)

    def __init__(
        self,
        sessao: Sessao,
        pasta_saida: Path,
        sobrescrever: bool = False,
        parent=None,
    ) -> None:
        super().__init__(sessao, parent)
        self.pasta_saida = pasta_saida
        self.sobrescrever = sobrescrever

    def run(self) -> None:  # noqa: D102
        try:
            relatorios: list[RelatorioDocumento] = self.sessao.processar_lote(
                self.pasta_saida,
                progresso=self._emitir,
                sobrescrever=self.sobrescrever,
            )
            self.concluido.emit(relatorios)
        except Exception as exc:  # pragma: no cover
            self.falhou.emit(f"Falha no processamento: {exc}")


def nova_sessao(cfg: Config) -> Sessao:
    return Sessao(cfg)
