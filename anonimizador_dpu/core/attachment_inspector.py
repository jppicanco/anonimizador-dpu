"""Inspeção de arquivos incorporados ao PDF.

Arquivos incorporados **nunca** são executados nem abertos por aplicativos
externos. A inspeção apenas descreve o que existe, para que o usuário decida.
Por padrão, os anexos são removidos do documento de saída; quando mantidos,
tornam-se pendência que impede a aprovação, porque o seu conteúdo não é
analisado por esta versão.
"""

from __future__ import annotations

from dataclasses import dataclass

import fitz

from .models import Risco, Severidade


@dataclass
class AnexoInfo:
    nome: str
    tamanho: int = 0
    tipo: str = ""
    descricao: str = ""
    suportado: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "nome": self.nome,
            "tamanho_bytes": self.tamanho,
            "tipo": self.tipo,
            "suportado_para_analise": self.suportado,
        }


#: Esta versão analisa apenas PDFs incorporados; demais formatos são pendência.
TIPOS_SUPORTADOS = ("application/pdf",)


def listar_anexos(doc: fitz.Document) -> list[AnexoInfo]:
    anexos: list[AnexoInfo] = []
    try:
        nomes = list(doc.embfile_names())
    except Exception:  # pragma: no cover
        return anexos
    for nome in nomes:
        info = AnexoInfo(nome=nome)
        try:
            dados = doc.embfile_info(nome) or {}
            info.tamanho = int(dados.get("size", 0) or 0)
            info.tipo = str(dados.get("ufilename", "") or dados.get("filename", "") or "")
            info.descricao = str(dados.get("desc", "") or "")
            mime = str(dados.get("mime", "") or "")
            info.suportado = mime in TIPOS_SUPORTADOS or info.tipo.lower().endswith(".pdf")
        except Exception:  # pragma: no cover
            info.descricao = "metadados do anexo não puderam ser lidos"
        anexos.append(info)
    return anexos


def riscos_de_anexos(anexos: list[AnexoInfo], serao_removidos: bool) -> list[Risco]:
    """Converte a lista de anexos em riscos, conforme o tratamento previsto."""
    if not anexos:
        return []
    nomes = ", ".join(a.nome for a in anexos[:10])
    if serao_removidos:
        return [
            Risco(
                "ANEXOS_REMOVIDOS",
                f"{len(anexos)} arquivo(s) incorporado(s) foram removidos do documento "
                "de saída. O conteúdo deles NÃO foi analisado nem anonimizado.",
                Severidade.AVISO,
                detalhe=nomes,
            )
        ]
    return [
        Risco(
            "ANEXOS_MANTIDOS",
            f"{len(anexos)} arquivo(s) incorporado(s) foram mantidos sem análise de "
            "conteúdo. O documento não pode ser considerado tratado.",
            Severidade.CRITICO,
            bloqueia_aprovacao=True,
            detalhe=nomes,
        )
    ]


def anexos_residuais(doc: fitz.Document) -> list[str]:
    """Anexos ainda presentes no documento de saída."""
    try:
        return list(doc.embfile_names())
    except Exception:  # pragma: no cover
        return []
