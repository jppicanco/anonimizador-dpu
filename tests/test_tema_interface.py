"""Contraste das cores da interface.

A tabela de revisão pinta o fundo de cada linha conforme a situação da
ocorrência. Quando o texto não é definido junto com o fundo, ele é herdado da
paleta do sistema — e, sob o tema escuro do Windows, ficava branco sobre fundo
claro, tornando a tabela ilegível. Estes testes fixam a regra: toda cor de
fundo prevista precisa ter um texto legível no tema a que pertence.

O limiar é o da WCAG 2.1 para texto normal (AA): razão de contraste de 4,5:1.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6.QtGui")

from PySide6.QtGui import QColor  # noqa: E402

from anonimizador_dpu.app.ui.tema import (  # noqa: E402
    contraste,
    cores_html,
    fundos_status,
    texto_sobre,
)
from anonimizador_dpu.core.models import Status  # noqa: E402

CONTRASTE_MINIMO = 4.5


@pytest.mark.parametrize("escuro", [False, True], ids=["tema_claro", "tema_escuro"])
def test_texto_legivel_sobre_todas_as_situacoes(escuro: bool) -> None:
    fundos = fundos_status(escuro=escuro)
    assert set(fundos) == set(Status), "toda situação precisa de cor própria"
    for status, fundo in fundos.items():
        razao = contraste(fundo, texto_sobre(fundo))
        assert razao >= CONTRASTE_MINIMO, (
            f"{status.value} no tema "
            f"{'escuro' if escuro else 'claro'}: contraste {razao:.2f}"
        )


@pytest.mark.parametrize("escuro", [False, True], ids=["tema_claro", "tema_escuro"])
def test_situacoes_distinguiveis_entre_si(escuro: bool) -> None:
    """Duas situações diferentes não podem ter exatamente a mesma cor."""
    fundos = fundos_status(escuro=escuro)
    assert len({c.name() for c in fundos.values()}) == len(fundos)


@pytest.mark.parametrize("escuro", [False, True], ids=["tema_claro", "tema_escuro"])
def test_faixas_de_confianca_legiveis(escuro: bool) -> None:
    """A coluna Confiança tem fundo próprio e também precisa contrastar."""
    from anonimizador_dpu.app.ui import tema

    cores = tema._CONFIANCA_ESCURO if escuro else tema._CONFIANCA_CLARO
    assert set(cores) == set(tema.ROTULOS_CONFIANCA)
    for faixa, valor in cores.items():
        fundo = QColor(valor)
        razao = contraste(fundo, texto_sobre(fundo))
        assert razao >= CONTRASTE_MINIMO, f"{faixa}: contraste {razao:.2f}"


def test_faixa_de_confianca_usa_os_limiares_configurados() -> None:
    from anonimizador_dpu.app.ui.tema import faixa_confianca
    from anonimizador_dpu.core.config import Config

    cfg = Config()
    assert faixa_confianca(0.99, cfg) == "alta"
    assert faixa_confianca(cfg.deteccao.limiar_auto_confirmacao, cfg) == "alta"
    assert faixa_confianca(0.80, cfg) == "media"
    assert faixa_confianca(cfg.deteccao.limiar_revisao_obrigatoria, cfg) == "media"
    assert faixa_confianca(0.50, cfg) == "baixa"


def test_texto_sobre_escolhe_o_extremo_certo() -> None:
    assert texto_sobre(QColor("#ffffff")).lightness() < 128
    assert texto_sobre(QColor("#000000")).lightness() > 128


def test_cores_html_cobrem_as_chaves_usadas() -> None:
    esperadas = {
        "erro",
        "alerta",
        "atencao",
        "ok",
        "aviso_fundo",
        "aviso_texto",
        "aviso_borda",
    }
    assert esperadas <= set(cores_html())


def test_tarja_de_aviso_legivel_nos_dois_temas() -> None:
    """A tarja de aviso define fundo e texto, e não pode depender da paleta."""
    from anonimizador_dpu.app.ui import tema

    for escuro in (False, True):
        cores = tema._HTML_ESCURO if escuro else tema._HTML_CLARO
        razao = contraste(QColor(cores["aviso_fundo"]), QColor(cores["aviso_texto"]))
        assert razao >= CONTRASTE_MINIMO, f"tarja de aviso: contraste {razao:.2f}"
