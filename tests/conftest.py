"""Configuração comum dos testes.

As fixtures sintéticas são geradas uma vez por sessão de teste em diretório
temporário. Nenhum processo judicial real é utilizado.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from anonimizador_dpu.core.config import Config  # noqa: E402
from anonimizador_dpu.core.ocr_engine import verificar_ocr  # noqa: E402
from tests.fixtures import gerador  # noqa: E402

#: Marcador para testes que dependem do Tesseract instalado na máquina.
ocr_disponivel = verificar_ocr(Config().ocr).disponivel
requer_ocr = pytest.mark.skipif(
    not ocr_disponivel, reason="Tesseract com idioma português não está instalado"
)


@pytest.fixture(scope="session")
def pasta_fixtures(tmp_path_factory) -> Path:
    pasta = tmp_path_factory.mktemp("fixtures_pdf")
    gerador.gerar_todas(pasta)
    return pasta


@pytest.fixture
def cfg() -> Config:
    """Configuração padrão com OCR em português."""
    configuracao = Config()
    configuracao.ocr.dpi = 200  # mais rápido nos testes, ainda legível
    return configuracao


@pytest.fixture
def pasta_saida(tmp_path) -> Path:
    destino = tmp_path / "saida"
    destino.mkdir()
    return destino


def confirmar_tudo(sessao, documento: str | None = None) -> int:
    """Simula a revisão humana confirmando todas as ocorrências pendentes."""
    from anonimizador_dpu.core.models import Status

    candidatos = (
        sessao.gerenciador.por_documento(documento)
        if documento
        else sessao.gerenciador.candidatos
    )
    total = 0
    for candidato in candidatos:
        if candidato.status in (Status.DETECTADO, Status.PENDENTE):
            candidato.status = Status.CONFIRMADO
            candidato.requer_revisao = False
            total += 1
    return total
