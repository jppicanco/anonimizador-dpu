"""Registro de auditoria com supressão de dados pessoais.

O log registra eventos de processamento (o que foi feito, quando, com qual
resultado), nunca o conteúdo dos autos. Um filtro adicional mascara padrões de
dados pessoais que porventura cheguem ao log por engano.
"""

from __future__ import annotations

import logging
import os
import re
import stat
from pathlib import Path

from .config import APP_ID, APP_VERSAO, diretorio_config

_NOME_LOGGER = "anonimizador_dpu"

#: Padrões mascarados antes de qualquer gravação em log.
_PADROES_PII: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF SUPRIMIDO]"),
    (re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b"), "[CNPJ SUPRIMIDO]"),
    (re.compile(r"\b\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}\b"), "[PROCESSO SUPRIMIDO]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[EMAIL SUPRIMIDO]"),
    (re.compile(r"\b\d{5}-?\d{3}\b"), "[CEP SUPRIMIDO]"),
    (re.compile(r"\(?\b\d{2}\)?\s?9?\d{4}-?\d{4}\b"), "[TELEFONE SUPRIMIDO]"),
)


class FiltroPII(logging.Filter):
    """Mascara padrões de dados pessoais na mensagem antes da gravação."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            mensagem = record.getMessage()
        except Exception:  # pragma: no cover - mensagem malformada
            return True
        limpo = mensagem
        for padrao, substituto in _PADROES_PII:
            limpo = padrao.sub(substituto, limpo)
        if limpo != mensagem:
            record.msg = limpo
            record.args = ()
        return True


def _stream_console():
    """Fluxo de console tolerante a acentuação em terminais Windows legados."""
    import io
    import sys

    destino = sys.stderr
    try:
        if destino is not None and hasattr(destino, "buffer"):
            return io.TextIOWrapper(
                destino.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:  # pragma: no cover - fluxo não reconfigurável
        pass
    return destino


def caminho_log() -> Path:
    return diretorio_config() / "logs" / f"{APP_ID}.log"


def configurar_log(nivel: str = "INFO", em_arquivo: bool = True) -> logging.Logger:
    """Configura o logger da aplicação. Idempotente."""
    logger = logging.getLogger(_NOME_LOGGER)
    if logger.handlers:
        return logger
    logger.setLevel(getattr(logging, str(nivel).upper(), logging.INFO))
    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    filtro = FiltroPII()

    console = logging.StreamHandler(_stream_console())
    console.setFormatter(formato)
    console.addFilter(filtro)
    logger.addHandler(console)

    if em_arquivo:
        try:
            destino = caminho_log()
            destino.parent.mkdir(parents=True, exist_ok=True)
            arquivo = logging.FileHandler(destino, encoding="utf-8")
            arquivo.setFormatter(formato)
            arquivo.addFilter(filtro)
            logger.addHandler(arquivo)
            try:
                os.chmod(destino, stat.S_IRUSR | stat.S_IWUSR)
            except OSError:
                pass
        except OSError:
            logger.warning("Não foi possível abrir o arquivo de log; usando apenas console.")

    logger.propagate = False
    logger.info("Anonimizador DPU %s — log iniciado (conteúdo dos autos nunca é registrado).", APP_VERSAO)
    return logger


def obter_logger(nome: str = "") -> logging.Logger:
    """Retorna um logger filho já submetido ao filtro de dados pessoais."""
    base = logging.getLogger(_NOME_LOGGER)
    if not base.handlers:
        configurar_log()
    return base.getChild(nome) if nome else base
