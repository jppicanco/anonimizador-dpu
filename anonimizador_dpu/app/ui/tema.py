"""Cores da interface, ajustadas ao tema claro ou escuro do sistema.

O Windows 11 e o Qt 6 seguem a preferência de tema do usuário. As cores de
situação eram definidas apenas para fundo claro; sob o tema escuro, o texto
herdado da paleta ficava branco sobre fundo pastel e tornava a tabela de
revisão ilegível.

Este módulo concentra as cores em um só lugar e resolve o contraste pelo
critério da WCAG 2.1, de modo que qualquer cor acrescentada depois continue
legível nos dois temas.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ...core.models import Status, Veredito

#: Luminância a partir da qual o texto preto contrasta melhor que o branco.
#: Ponto de equilíbrio da fórmula de contraste da WCAG 2.1.
_LIMIAR_LUMINANCIA = 0.179

_TEXTO_CLARO = QColor("#f2f2f2")
_TEXTO_ESCURO = QColor("#141414")


def tema_escuro() -> bool:
    """Informa se a paleta ativa do aplicativo é escura."""
    app = QApplication.instance()
    if app is None:
        return False
    return app.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _luminancia(cor: QColor) -> float:
    def canal(valor: int) -> float:
        v = valor / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * canal(cor.red())
        + 0.7152 * canal(cor.green())
        + 0.0722 * canal(cor.blue())
    )


def texto_sobre(fundo: QColor) -> QColor:
    """Devolve a cor de texto que melhor contrasta com ``fundo``."""
    return _TEXTO_ESCURO if _luminancia(fundo) > _LIMIAR_LUMINANCIA else _TEXTO_CLARO


_FUNDOS_STATUS_CLARO = {
    Status.DETECTADO: "#fff3cd",
    Status.CONFIRMADO: "#d4edda",
    Status.REJEITADO: "#e2e3e5",
    Status.PENDENTE: "#ffe0b2",
    Status.REDIGIDO: "#cfe2ff",
    Status.VERIFICADO: "#c3e6cb",
    Status.FALHA_CRITICA: "#f5c6cb",
}

_FUNDOS_STATUS_ESCURO = {
    Status.DETECTADO: "#4a3d12",
    Status.CONFIRMADO: "#1d3a27",
    Status.REJEITADO: "#36383a",
    Status.PENDENTE: "#523512",
    Status.REDIGIDO: "#1b3350",
    Status.VERIFICADO: "#214d32",
    Status.FALHA_CRITICA: "#52202a",
}


def fundos_status(escuro: bool | None = None) -> dict[Status, QColor]:
    """Cor de fundo de cada situação.

    Sem argumento, segue o tema ativo; ``escuro`` permite consultar um tema
    específico, o que os testes usam para conferir o contraste dos dois.
    """
    if escuro is None:
        escuro = tema_escuro()
    origem = _FUNDOS_STATUS_ESCURO if escuro else _FUNDOS_STATUS_CLARO
    return {status: QColor(valor) for status, valor in origem.items()}


def contraste(primeira: QColor, segunda: QColor) -> float:
    """Razão de contraste entre duas cores, conforme a WCAG 2.1."""
    a, b = sorted((_luminancia(primeira), _luminancia(segunda)), reverse=True)
    return (a + 0.05) / (b + 0.05)


#: Faixas de certeza da detecção, usadas na coluna "Confiança".
ROTULOS_CONFIANCA = {
    "alta": "Confiança alta: formato inequívoco ou rótulo explícito.",
    "media": "Confiança média: confira antes de deixar sair.",
    "baixa": "Confiança baixa: a detecção pode estar errada — vale olhar.",
}

_CONFIANCA_CLARO = {"alta": "#d4edda", "media": "#fff3cd", "baixa": "#ffd9b3"}
_CONFIANCA_ESCURO = {"alta": "#1d3a27", "media": "#4a3d12", "baixa": "#5c3512"}


def cores_confianca() -> dict[str, QColor]:
    """Cor de fundo de cada faixa de confiança, conforme o tema ativo."""
    origem = _CONFIANCA_ESCURO if tema_escuro() else _CONFIANCA_CLARO
    return {faixa: QColor(valor) for faixa, valor in origem.items()}


def faixa_confianca(confianca: float, cfg) -> str:
    """Classifica a confiança usando os limiares configurados."""
    if confianca >= cfg.deteccao.limiar_auto_confirmacao:
        return "alta"
    if confianca >= cfg.deteccao.limiar_revisao_obrigatoria:
        return "media"
    return "baixa"


def fundo_neutro() -> QColor:
    """Fundo das linhas sem situação conhecida."""
    app = QApplication.instance()
    if app is None:
        return QColor("#ffffff")
    return app.palette().color(QPalette.ColorRole.Base)


# --------------------------------------------------------------------- HTML
# Cores usadas nos painéis de texto (QTextBrowser), onde o fundo é o da paleta
# do sistema. No tema escuro, os tons originais ficavam escuros demais.

_HTML_CLARO = {
    "erro": "#c0392b",
    "alerta": "#b9770e",
    "atencao": "#ca6f1e",
    "ok": "#1e8449",
    "aviso_fundo": "#fff4e5",
    "aviso_texto": "#5b3a00",
    "aviso_borda": "#e08700",
}

_HTML_ESCURO = {
    "erro": "#ff7a6b",
    "alerta": "#e8a33d",
    "atencao": "#f0a35e",
    "ok": "#5cc98a",
    "aviso_fundo": "#4a3715",
    "aviso_texto": "#ffe6bd",
    "aviso_borda": "#e08700",
}


def cores_html() -> dict[str, str]:
    """Cores em notação CSS para os painéis de texto, conforme o tema."""
    return dict(_HTML_ESCURO if tema_escuro() else _HTML_CLARO)


def cores_veredito() -> dict[Veredito, str]:
    """Cor de destaque de cada veredito, conforme o tema."""
    c = cores_html()
    return {
        Veredito.APROVADO_TESTES: c["ok"],
        Veredito.APROVADO_COM_RESSALVAS: c["alerta"],
        Veredito.REVISAO_OBRIGATORIA: c["atencao"],
        Veredito.REPROVADO: c["erro"],
    }


_ACAO_CLARO = {
    "fundo": "#1565c0",
    "hover": "#0d47a1",
    "texto": "#ffffff",
    "inativo": "#cfd4d9",
    "inativo_texto": "#8a9099",
}
_ACAO_ESCURO = {
    "fundo": "#1e6fd9",
    "hover": "#2f86f0",
    "texto": "#ffffff",
    "inativo": "#2e3136",
    "inativo_texto": "#70757c",
}


def estilo_botao_principal() -> str:
    """Folha de estilo do botão que conclui cada etapa.

    O botão de ação ficava igual aos demais e se perdia no rodapé da tela.
    Aqui ele ganha cor própria, altura e negrito, para ser o destino óbvio
    depois da revisão.
    """
    c = _ACAO_ESCURO if tema_escuro() else _ACAO_CLARO
    return (
        "QPushButton {"
        f" background-color: {c['fundo']}; color: {c['texto']};"
        " border: none; border-radius: 4px;"
        " padding: 10px 18px; font-weight: 600; font-size: 14px;"
        " }"
        f"QPushButton:hover {{ background-color: {c['hover']}; }}"
        # O estado inativo precisa de cor própria: herdar da paleta produzia
        # uma barra clara e chamativa justamente quando o botão não serve.
        f"QPushButton:disabled {{ background-color: {c['inativo']};"
        f" color: {c['inativo_texto']}; }}"
    )


def estilo_aplicacao() -> str:
    """Acabamento geral da janela.

    Ajustes discretos, de propósito: respiro nas abas e nos grupos, cabeçalho
    de tabela legível e linhas mais altas. Nada que descaracterize o visual
    nativo do sistema nem que dependa de cor fixa de fundo.
    """
    escuro = tema_escuro()
    grade = "#3a3a3a" if escuro else "#d8d8d8"
    realce = "#4a4a4a" if escuro else "#e8e8e8"
    return f"""
    QTabBar::tab {{ padding: 7px 14px; margin-right: 2px; }}
    QTabBar::tab:selected {{ font-weight: 600; }}
    QGroupBox {{ margin-top: 10px; padding-top: 6px; border: 1px solid {grade};
                 border-radius: 4px; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px;
                        font-weight: 600; }}
    QHeaderView::section {{ padding: 6px 8px; border: none;
                            border-right: 1px solid {grade};
                            border-bottom: 1px solid {grade};
                            background-color: {realce}; font-weight: 600; }}
    QTableWidget {{ gridline-color: {grade}; }}
    QTableWidget::item {{ padding: 4px 6px; }}
    QPushButton {{ padding: 6px 12px; }}
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {{
        padding: 4px 6px; }}
    """


def estilo_aviso() -> str:
    """Folha de estilo da tarja de aviso permanente."""
    c = cores_html()
    return (
        f"background:{c['aviso_fundo']}; border-left:6px solid {c['aviso_borda']}; "
        f"padding:8px; color:{c['aviso_texto']};"
    )
