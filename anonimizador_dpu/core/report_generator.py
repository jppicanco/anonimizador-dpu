"""Geração dos relatórios técnicos (JSON e HTML).

O relatório é construído para auditoria, não para arquivar dados sigilosos.
Por padrão ele não contém: CPFs, nomes, endereços, trechos dos autos ou o texto
extraído. Cada ocorrência aparece apenas com categoria, página, origem,
confiança, status, pseudônimo, valor mascarado e um hash salgado por sessão.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from .config import AVISO_ASSINATURA, AVISO_PRINCIPAL, AVISO_SSD, Config, info_ambiente
from .models import (
    ROTULOS_VEREDITO,
    Candidato,
    RelatorioDocumento,
    Risco,
    Veredito,
    rotulo_categoria,
)


def _riscos(lista: list[Risco]) -> list[dict]:
    return [r.to_dict() for r in lista]


def montar_json(relatorio: RelatorioDocumento, cfg: Config) -> dict:
    """Monta a estrutura do relatório técnico de um documento."""
    insp = relatorio.inspecao
    red = relatorio.redacao
    val = relatorio.validacao
    candidatos: list[Candidato] = relatorio.candidatos

    por_categoria: dict[str, int] = {}
    for c in candidatos:
        chave = rotulo_categoria(c.categoria)
        por_categoria[chave] = por_categoria.get(chave, 0) + 1

    def _contar(status: str) -> int:
        return len([c for c in candidatos if c.status.value == status])

    dados = {
        "aplicativo": info_ambiente(),
        "aviso": AVISO_PRINCIPAL,
        "avisos_adicionais": [AVISO_SSD, AVISO_ASSINATURA],
        "documento": {
            "arquivo_entrada": relatorio.arquivo_entrada,
            "arquivo_saida": relatorio.arquivo_saida,
            "sha256_entrada": insp.sha256_entrada if insp else "",
            "sha256_saida": red.sha256_saida if red else "",
            "processado_em": relatorio.inicio.strftime("%d/%m/%Y %H:%M:%S"),
            "concluido_em": relatorio.fim.strftime("%d/%m/%Y %H:%M:%S")
            if relatorio.fim
            else None,
            "duracao_s": round((relatorio.fim - relatorio.inicio).total_seconds(), 1)
            if relatorio.fim
            else None,
            "cancelado": relatorio.cancelado,
            "erro": relatorio.erro,
        },
        "estrutura": insp.to_dict() if insp else {},
        "cobertura": {
            "paginas_total": insp.total_paginas if insp else 0,
            "paginas_processadas_por_texto": relatorio.paginas_por_texto,
            "paginas_processadas_por_ocr": relatorio.paginas_por_ocr,
            "paginas_nao_examinadas": [p + 1 for p in relatorio.paginas_nao_examinadas],
        },
        "ocorrencias": {
            "total": len(candidatos),
            "por_categoria": por_categoria,
            "confirmadas": _contar("CONFIRMADO"),
            "rejeitadas": _contar("REJEITADO"),
            "pendentes": _contar("PENDENTE") + _contar("DETECTADO"),
            "redigidas": _contar("REDIGIDO"),
            "verificadas": _contar("VERIFICADO"),
            "falhas_criticas": _contar("FALHA_CRITICA"),
            "detalhe": [c.to_dict() for c in candidatos],
        },
        "redacao": {
            "areas_aplicadas": red.redacoes_aplicadas if red else 0,
            "areas_texto": red.redacoes_texto if red else 0,
            "areas_imagem": red.redacoes_imagem if red else 0,
            "paginas_reconstruidas": [p + 1 for p in (red.paginas_rasterizadas if red else [])],
            "metadados_removidos": red.metadados_removidos if red else [],
            "estruturas_removidas": red.estruturas_removidas if red else [],
            "estruturas_nao_tratadas": red.estruturas_nao_tratadas if red else [],
            "falhas": _riscos(red.falhas) if red else [],
        },
        "validacao": {
            "veredito": val.veredito.value if val else Veredito.REVISAO_OBRIGATORIA.value,
            "veredito_rotulo": ROTULOS_VEREDITO.get(
                val.veredito if val else Veredito.REVISAO_OBRIGATORIA, ""
            ),
            "abriu_corretamente": val.abriu_corretamente if val else False,
            "paginas_verificadas_texto": val.paginas_verificadas_texto if val else 0,
            "paginas_verificadas_ocr": val.paginas_verificadas_ocr if val else 0,
            "paginas_sem_cobertura": [p + 1 for p in (val.paginas_sem_cobertura if val else [])],
            "areas_conferidas": val.areas_redacao_conferidas if val else 0,
            "areas_com_falha": [p + 1 for p in (val.areas_redacao_falhas if val else [])],
            "ocorrencias_residuais": len(val.residuais) if val else 0,
            "identificadores_residuais_conhecidos": val.residuais_conhecidos if val else 0,
            "metadados_residuais": val.metadados_residuais if val else [],
            "anexos_residuais": val.anexos_residuais if val else [],
            "riscos": _riscos(val.riscos) if val else [],
            "observacoes": val.observacoes if val else [],
        },
        "politica": {
            "categorias_ativas": sorted(cfg.categorias_ativas),
            "modo_redacao": cfg.redacao.modo,
            "ocr_idiomas": cfg.ocr.idiomas,
            "ocr_dpi": cfg.ocr.dpi,
            "limiar_auto_confirmacao": cfg.deteccao.limiar_auto_confirmacao,
            "anonimiza_profissionais": cfg.deteccao.anonimizar_profissionais,
            "tabela_reversao_gerada": cfg.permitir_tabela_reversao,
        },
        "avisos_execucao": relatorio.avisos,
    }
    return dados


def salvar_json(relatorio: RelatorioDocumento, cfg: Config, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(montar_json(relatorio, cfg), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return destino


# ------------------------------------------------------------------- HTML
_CSS = """
body { font-family: Segoe UI, Arial, sans-serif; margin: 24px; color: #1b1b1b; }
h1 { font-size: 20px; border-bottom: 2px solid #003366; padding-bottom: 6px; }
h2 { font-size: 15px; margin-top: 24px; color: #003366; }
table { border-collapse: collapse; width: 100%; font-size: 12px; margin-top: 8px; }
th, td { border: 1px solid #c7c7c7; padding: 4px 6px; text-align: left; vertical-align: top; }
th { background: #eef2f7; }
.aviso { background: #fff4e5; border-left: 5px solid #e08700; padding: 10px; margin: 12px 0; }
.critico { background: #fdecea; border-left: 5px solid #c0392b; padding: 10px; margin: 12px 0; }
.ok { background: #e9f7ef; border-left: 5px solid #1e8449; padding: 10px; margin: 12px 0; }
.veredito { font-size: 16px; font-weight: bold; padding: 10px; margin: 12px 0; }
.v-APROVADO_NOS_TESTES_AUTOMATIZADOS { background: #e9f7ef; border: 2px solid #1e8449; }
.v-APROVADO_COM_RESSALVAS { background: #fff4e5; border: 2px solid #e08700; }
.v-REVISAO_OBRIGATORIA { background: #fdf2e9; border: 2px solid #ca6f1e; }
.v-REPROVADO { background: #fdecea; border: 2px solid #c0392b; }
small { color: #555; }
"""


def _tabela(cabecalhos: list[str], linhas: list[list[str]]) -> str:
    cabecalho = "".join(f"<th>{html.escape(c)}</th>" for c in cabecalhos)
    corpo = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(v))}</td>" for v in linha) + "</tr>"
        for linha in linhas
    )
    return f"<table><tr>{cabecalho}</tr>{corpo}</table>"


def montar_html(relatorio: RelatorioDocumento, cfg: Config) -> str:
    """Gera o relatório em HTML, sem dados pessoais originais."""
    dados = montar_json(relatorio, cfg)
    veredito = dados["validacao"]["veredito"]
    rotulo = dados["validacao"]["veredito_rotulo"]

    partes: list[str] = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>Relatório de anonimização — {html.escape(relatorio.arquivo_entrada)}</title>",
        f"<style>{_CSS}</style></head><body>",
        "<h1>Relatório de anonimização</h1>",
        f"<div class='veredito v-{veredito}'>{html.escape(rotulo)}</div>",
        f"<div class='aviso'><strong>Aviso:</strong> {html.escape(AVISO_PRINCIPAL)}</div>",
    ]

    doc = dados["documento"]
    partes.append("<h2>Documento</h2>")
    partes.append(
        _tabela(
            ["Campo", "Valor"],
            [
                ["Arquivo de entrada", doc["arquivo_entrada"]],
                ["Arquivo de saída", doc["arquivo_saida"]],
                ["SHA-256 da entrada", doc["sha256_entrada"]],
                ["SHA-256 da saída", doc["sha256_saida"]],
                ["Processado em", doc["processado_em"]],
                ["Concluído em", doc["concluido_em"] or "—"],
                ["Duração (s)", doc["duracao_s"] if doc["duracao_s"] is not None else "—"],
                ["Versão do aplicativo", dados["aplicativo"]["versao"]],
            ],
        )
    )

    cob = dados["cobertura"]
    partes.append("<h2>Cobertura do exame</h2>")
    partes.append(
        _tabela(
            ["Métrica", "Valor"],
            [
                ["Páginas no documento", cob["paginas_total"]],
                ["Páginas examinadas por texto", cob["paginas_processadas_por_texto"]],
                ["Páginas examinadas por OCR", cob["paginas_processadas_por_ocr"]],
                [
                    "Páginas não examinadas integralmente",
                    ", ".join(str(p) for p in cob["paginas_nao_examinadas"]) or "nenhuma",
                ],
            ],
        )
    )

    oc = dados["ocorrencias"]
    partes.append("<h2>Ocorrências</h2>")
    partes.append(
        _tabela(
            ["Situação", "Quantidade"],
            [
                ["Total detectado", oc["total"]],
                ["Confirmadas", oc["confirmadas"]],
                ["Rejeitadas (falsos positivos)", oc["rejeitadas"]],
                ["Pendentes de decisão", oc["pendentes"]],
                ["Redigidas", oc["redigidas"]],
                ["Verificadas após a redação", oc["verificadas"]],
                ["Falhas críticas", oc["falhas_criticas"]],
            ],
        )
    )
    if oc["por_categoria"]:
        partes.append("<h2>Ocorrências por categoria</h2>")
        partes.append(
            _tabela(
                ["Categoria", "Quantidade"],
                [[k, v] for k, v in sorted(oc["por_categoria"].items())],
            )
        )

    red = dados["redacao"]
    partes.append("<h2>Redação aplicada</h2>")
    partes.append(
        _tabela(
            ["Métrica", "Valor"],
            [
                ["Áreas redigidas", red["areas_aplicadas"]],
                ["Áreas em camada de texto", red["areas_texto"]],
                ["Áreas em imagem", red["areas_imagem"]],
                [
                    "Páginas reconstruídas por renderização",
                    ", ".join(str(p) for p in red["paginas_reconstruidas"]) or "nenhuma",
                ],
                ["Metadados removidos", ", ".join(red["metadados_removidos"]) or "nenhum"],
                [
                    "Estruturas removidas",
                    "; ".join(red["estruturas_removidas"]) or "nenhuma",
                ],
                [
                    "Estruturas NÃO tratadas",
                    "; ".join(red["estruturas_nao_tratadas"]) or "nenhuma",
                ],
            ],
        )
    )

    val = dados["validacao"]
    partes.append("<h2>Validação independente</h2>")
    partes.append(
        _tabela(
            ["Verificação", "Resultado"],
            [
                ["Arquivo reaberto com sucesso", "sim" if val["abriu_corretamente"] else "NÃO"],
                ["Páginas reextraídas (texto)", val["paginas_verificadas_texto"]],
                ["Páginas reexaminadas por OCR", val["paginas_verificadas_ocr"]],
                [
                    "Páginas sem cobertura adequada",
                    ", ".join(str(p) for p in val["paginas_sem_cobertura"]) or "nenhuma",
                ],
                ["Áreas de redação conferidas", val["areas_conferidas"]],
                [
                    "Áreas com falha",
                    ", ".join(str(p) for p in val["areas_com_falha"]) or "nenhuma",
                ],
                ["Ocorrências detectadas na saída", val["ocorrencias_residuais"]],
                [
                    "Identificadores originais ainda recuperáveis",
                    val["identificadores_residuais_conhecidos"],
                ],
                ["Metadados residuais", ", ".join(val["metadados_residuais"]) or "nenhum"],
                ["Anexos residuais", ", ".join(val["anexos_residuais"]) or "nenhum"],
            ],
        )
    )

    riscos = val["riscos"] + red["falhas"]
    if riscos:
        partes.append("<h2>Riscos e pendências</h2>")
        partes.append(
            _tabela(
                ["Código", "Severidade", "Página", "Bloqueia aprovação", "Descrição"],
                [
                    [
                        r["codigo"],
                        r["severidade"],
                        r["pagina"] or "—",
                        "sim" if r["bloqueia_aprovacao"] else "não",
                        r["descricao"],
                    ]
                    for r in riscos
                ],
            )
        )

    if val["observacoes"]:
        partes.append("<h2>Observações</h2><ul>")
        partes.extend(f"<li>{html.escape(o)}</li>" for o in val["observacoes"])
        partes.append("</ul>")

    partes.append("<h2>Limites desta verificação</h2>")
    partes.append(
        "<div class='critico'><ul>"
        "<li>A aprovação automatizada cobre apenas os testes definidos nesta versão: "
        "reextração de texto, OCR local, conferência de áreas, metadados e anexos.</li>"
        "<li>A ausência de detecções não prova anonimização integral. Dados pessoais "
        "podem permanecer em formas não cobertas pelos detectores.</li>"
        "<li>A reidentificação por contexto (narrativa, datas, relações) não é tratada.</li>"
        f"<li>{html.escape(AVISO_SSD)}</li>"
        f"<li>{html.escape(AVISO_ASSINATURA)}</li>"
        "</ul></div>"
    )

    partes.append(
        f"<p><small>Relatório gerado em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')} "
        f"pelo {html.escape(dados['aplicativo']['aplicativo'])} "
        f"{html.escape(dados['aplicativo']['versao'])}. Nenhum dado pessoal original "
        "é registrado neste relatório.</small></p>"
    )
    partes.append("</body></html>")
    return "".join(partes)


def salvar_html(relatorio: RelatorioDocumento, cfg: Config, destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(montar_html(relatorio, cfg), encoding="utf-8")
    return destino


def resumo_lote(relatorios: list[RelatorioDocumento]) -> dict:
    """Resumo da execução de um lote de documentos."""
    por_veredito: dict[str, int] = {}
    for r in relatorios:
        chave = r.veredito.value
        por_veredito[chave] = por_veredito.get(chave, 0) + 1
    return {
        "documentos": len(relatorios),
        "por_veredito": por_veredito,
        "aprovados_nos_testes": por_veredito.get(Veredito.APROVADO_TESTES.value, 0),
        "com_pendencias": sum(
            v
            for k, v in por_veredito.items()
            if k != Veredito.APROVADO_TESTES.value
        ),
        "arquivos": [
            {
                "entrada": r.arquivo_entrada,
                "saida": r.arquivo_saida,
                "veredito": r.veredito.value,
                "erro": r.erro,
            }
            for r in relatorios
        ],
        "aviso": AVISO_PRINCIPAL,
    }


def salvar_resumo_lote(relatorios: list[RelatorioDocumento], destino: Path) -> Path:
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(resumo_lote(relatorios), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return destino
