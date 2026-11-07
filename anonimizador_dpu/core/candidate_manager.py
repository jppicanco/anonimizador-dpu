"""Gerenciamento de candidatos: deduplicação, entidades e pseudônimos.

Responsabilidades:

* unir a mesma ocorrência vista no texto nativo e no OCR, sem contá-la duas
  vezes e sem perder nenhuma das áreas a redigir;
* agrupar ocorrências que se referem à mesma entidade (mesma pessoa, mesmo CPF)
  ao longo de todos os documentos do lote, garantindo pseudônimos consistentes;
* permitir que o usuário separe pessoas distintas com nomes iguais;
* aplicar decisões individuais ou em lote;
* manter a associação pseudônimo → valor original apenas em memória.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .brazilian_validators import somente_digitos
from .models import Candidato, Categoria, Origem, Papel, Status

#: Categorias cujo valor é essencialmente numérico: a chave de entidade ignora
#: a pontuação, de modo que "529.982.247-25" e "52998224725" sejam a mesma entidade.
CATEGORIAS_NUMERICAS = frozenset(
    {
        Categoria.CPF,
        Categoria.CNPJ,
        Categoria.CEP,
        Categoria.TELEFONE,
        Categoria.PROCESSO_CNJ,
        Categoria.TITULO_ELEITOR,
        Categoria.NIT_PIS_PASEP,
        Categoria.CNH,
        Categoria.BENEFICIO_NB,
        Categoria.CARTAO,
        Categoria.CONTA_BANCARIA,
        Categoria.AGENCIA_BANCARIA,
        Categoria.MATRICULA,
        Categoria.PROTOCOLO,
    }
)

#: Prefixo do pseudônimo por categoria.
PREFIXO_PSEUDONIMO: dict[Categoria, str] = {
    Categoria.NOME_PESSOA: "PESSOA",
    Categoria.CPF: "CPF",
    Categoria.CNPJ: "CNPJ",
    Categoria.RG: "DOCUMENTO",
    Categoria.CNH: "CNH",
    Categoria.PASSAPORTE: "PASSAPORTE",
    Categoria.TITULO_ELEITOR: "TITULO",
    Categoria.NIT_PIS_PASEP: "NIT",
    Categoria.DATA_NASCIMENTO: "DATA_NASC",
    Categoria.ASSINATURA: "ASSINATURA",
    Categoria.ENDERECO: "ENDERECO",
    Categoria.LOCALIDADE: "LOCAL",
    Categoria.CEP: "CEP",
    Categoria.TELEFONE: "TELEFONE",
    Categoria.EMAIL: "EMAIL",
    Categoria.CONTA_BANCARIA: "CONTA",
    Categoria.AGENCIA_BANCARIA: "AGENCIA",
    Categoria.CHAVE_PIX: "PIX",
    Categoria.CARTAO: "CARTAO",
    Categoria.PROCESSO_CNJ: "PROCESSO",
    Categoria.PROTOCOLO: "PROTOCOLO",
    Categoria.BENEFICIO_NB: "BENEFICIO",
    Categoria.MATRICULA: "MATRICULA",
    Categoria.DADO_SAUDE: "DADO_SAUDE",
    Categoria.PLACA_VEICULO: "PLACA",
    Categoria.URL_COM_TOKEN: "ENDERECO_ELETRONICO",
    Categoria.REGIAO_MANUAL: "AREA",
    Categoria.OUTRO: "DADO",
}

#: Para nomes de pessoa, o papel processual determina o prefixo do pseudônimo.
PREFIXO_PAPEL: dict[Papel, str] = {
    Papel.ASSISTIDO: "ASSISTIDO",
    Papel.REQUERENTE: "REQUERENTE",
    Papel.REQUERIDO: "REQUERIDO",
    Papel.TESTEMUNHA: "TESTEMUNHA",
    Papel.ADVOGADO: "ADVOGADO",
    Papel.DEFENSOR: "DEFENSOR",
    Papel.MAGISTRADO: "MAGISTRADO",
    Papel.PERITO: "PERITO",
    Papel.SERVIDOR: "SERVIDOR",
    Papel.FAMILIAR: "FAMILIAR",
    Papel.CRIANCA_ADOLESCENTE: "MENOR",
    Papel.TERCEIRO: "TERCEIRO",
}


def _normalizar_texto(valor: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", valor) if unicodedata.category(c) != "Mn"
    )
    return re.sub(r"\s+", " ", sem_acento).strip().lower()


def chave_entidade(categoria: Categoria, valor: str) -> str:
    """Chave de agrupamento de uma entidade.

    Para nomes, usa o nome completo normalizado — nunca apenas o primeiro nome,
    para não unir pessoas distintas que compartilham o prenome.
    """
    if categoria in CATEGORIAS_NUMERICAS:
        digitos = somente_digitos(valor)
        if digitos:
            return f"{categoria.value}#{digitos}"
    return f"{categoria.value}#{_normalizar_texto(valor)}"


@dataclass
class Entidade:
    """Uma entidade distinta (pessoa, documento, endereço) e seu pseudônimo."""

    chave: str
    categoria: Categoria
    pseudonimo: str
    papel: Papel | None = None
    valores: set[str] = field(default_factory=set)
    documentos: set[str] = field(default_factory=set)
    ocorrencias: int = 0


class GerenciadorCandidatos:
    """Mantém o conjunto de candidatos de uma sessão de trabalho.

    A instância vive apenas durante a sessão; nada é gravado em disco por ela.
    """

    def __init__(self) -> None:
        self.candidatos: list[Candidato] = []
        self.entidades: dict[str, Entidade] = {}
        self._contadores: dict[str, int] = defaultdict(int)
        self._por_id: dict[str, Candidato] = {}

    # -------------------------------------------------------------- inclusão
    def adicionar(self, novos: list[Candidato]) -> None:
        for candidato in novos:
            existente = self._equivalente_na_pagina(candidato)
            if existente is not None:
                self._unir(existente, candidato)
                continue
            self.candidatos.append(candidato)
            self._por_id[candidato.id] = candidato
        self.atribuir_pseudonimos()

    def _equivalente_na_pagina(self, candidato: Candidato) -> Candidato | None:
        """Localiza a mesma ocorrência já registrada por outra fonte na página.

        A união só acontece entre fontes distintas (texto nativo e OCR). Duas
        ocorrências do mesmo valor vindas da mesma fonte são ocorrências
        diferentes do documento: cada uma tem a sua posição e pode pertencer a
        pessoas distintas (homônimos), de modo que não são fundidas.
        """
        if candidato.origem not in (Origem.TEXTO, Origem.OCR):
            return None
        chave = chave_entidade(candidato.categoria, candidato.valor)
        complementar = Origem.OCR if candidato.origem == Origem.TEXTO else Origem.TEXTO
        for existente in self.candidatos:
            if (
                existente.documento == candidato.documento
                and existente.pagina == candidato.pagina
                and existente.origem in (complementar, Origem.TEXTO_E_OCR)
                and chave_entidade(existente.categoria, existente.valor) == chave
            ):
                return existente
        return None

    @staticmethod
    def _unir(destino: Candidato, origem: Candidato) -> None:
        """Funde duas detecções da mesma ocorrência (texto e OCR) em uma só.

        As áreas de ambas as origens são preservadas: a camada textual e a
        camada de imagem precisam ser redigidas separadamente.
        """
        if destino.origem != origem.origem:
            destino.origem = Origem.TEXTO_E_OCR
        for bbox in origem.bboxes:
            if bbox not in destino.bboxes:
                destino.bboxes.append(bbox)
        destino.confianca = max(destino.confianca, origem.confianca)
        destino.ocorrencias_texto += 1
        if origem.papel and not destino.papel:
            destino.papel = origem.papel
        if origem.bbox_incerta and not origem.bboxes:
            destino.bbox_incerta = destino.bbox_incerta or not destino.bboxes
        else:
            destino.bbox_incerta = not destino.bboxes
        if destino.bboxes and destino.status == Status.PENDENTE and not destino.requer_revisao:
            destino.status = Status.DETECTADO

    # ------------------------------------------------------------ pseudônimos
    def atribuir_pseudonimos(self) -> None:
        """Atribui pseudônimos estáveis por entidade, em toda a sessão."""
        for candidato in self.candidatos:
            if candidato.entidade_id is None:
                candidato.entidade_id = chave_entidade(candidato.categoria, candidato.valor)
            entidade = self.entidades.get(candidato.entidade_id)
            if entidade is None:
                prefixo = self._prefixo(candidato)
                self._contadores[prefixo] += 1
                entidade = Entidade(
                    chave=candidato.entidade_id,
                    categoria=candidato.categoria,
                    pseudonimo=f"[{prefixo}_{self._contadores[prefixo]}]",
                    papel=candidato.papel,
                )
                self.entidades[candidato.entidade_id] = entidade
            entidade.valores.add(candidato.valor)
            entidade.documentos.add(candidato.documento)
            entidade.ocorrencias += 1
            candidato.pseudonimo = entidade.pseudonimo

    def _prefixo(self, candidato: Candidato) -> str:
        if candidato.categoria == Categoria.NOME_PESSOA and candidato.papel:
            return PREFIXO_PAPEL.get(candidato.papel, "PESSOA")
        return PREFIXO_PSEUDONIMO.get(candidato.categoria, "DADO")

    def separar_entidade(self, candidato_id: str, rotulo: str = "") -> str | None:
        """Separa uma ocorrência em nova entidade (pessoas distintas, nomes iguais)."""
        candidato = self._por_id.get(candidato_id)
        if candidato is None:
            return None
        sufixo = _normalizar_texto(rotulo) or candidato.id
        candidato.entidade_id = f"{candidato.entidade_id}@{sufixo}"
        prefixo = self._prefixo(candidato)
        self._contadores[prefixo] += 1
        entidade = Entidade(
            chave=candidato.entidade_id,
            categoria=candidato.categoria,
            pseudonimo=f"[{prefixo}_{self._contadores[prefixo]}]",
            papel=candidato.papel,
        )
        entidade.valores.add(candidato.valor)
        entidade.documentos.add(candidato.documento)
        entidade.ocorrencias = 1
        self.entidades[candidato.entidade_id] = entidade
        candidato.pseudonimo = entidade.pseudonimo
        return entidade.pseudonimo

    def definir_papel(self, candidato_id: str, papel: Papel | None) -> None:
        """Altera o papel processual e recalcula o pseudônimo da entidade."""
        candidato = self._por_id.get(candidato_id)
        if candidato is None:
            return
        candidato.papel = papel
        entidade = self.entidades.get(candidato.entidade_id or "")
        if entidade is not None:
            entidade.papel = papel
            prefixo = self._prefixo(candidato)
            self._contadores[prefixo] += 1
            entidade.pseudonimo = f"[{prefixo}_{self._contadores[prefixo]}]"
            for outro in self.candidatos:
                if outro.entidade_id == entidade.chave:
                    outro.pseudonimo = entidade.pseudonimo

    # -------------------------------------------------------------- decisões
    def obter(self, candidato_id: str) -> Candidato | None:
        return self._por_id.get(candidato_id)

    def definir_status(self, candidato_id: str, status: Status) -> None:
        candidato = self._por_id.get(candidato_id)
        if candidato is None:
            return
        candidato.status = status
        if status in (Status.CONFIRMADO, Status.REJEITADO):
            candidato.requer_revisao = False

    def suprimir_por_valor(
        self, valores: set[str], documento: str | None = None, motivo: str = ""
    ) -> int:
        """Mantém no texto todas as ocorrências cujos valores estão em ``valores``.

        Usado para aplicar a política de profissionais por pessoa: se o nome é
        de um profissional em algum ponto do documento, nenhuma de suas
        ocorrências é redigida. Redigir só algumas deixaria o nome legível no
        arquivo e tornaria a redação inútil.
        """
        alterados = 0
        for candidato in self.candidatos:
            if documento and candidato.documento != documento:
                continue
            if candidato.categoria is not Categoria.NOME_PESSOA:
                continue
            if _normalizar_texto(candidato.valor) not in valores:
                continue
            if candidato.status is Status.REJEITADO:
                continue
            candidato.status = Status.REJEITADO
            candidato.requer_revisao = False
            if motivo:
                candidato.motivo = motivo
            alterados += 1
        return alterados

    def definir_categoria(self, candidato_id: str, categoria: Categoria) -> None:
        candidato = self._por_id.get(candidato_id)
        if candidato is None:
            return
        candidato.categoria = categoria
        candidato.entidade_id = chave_entidade(categoria, candidato.valor)
        self.atribuir_pseudonimos()

    def equivalentes(self, candidato_id: str) -> list[Candidato]:
        """Ocorrências equivalentes (mesma entidade) em todos os documentos."""
        candidato = self._por_id.get(candidato_id)
        if candidato is None:
            return []
        return [c for c in self.candidatos if c.entidade_id == candidato.entidade_id]

    def aplicar_em_equivalentes(self, candidato_id: str, status: Status) -> int:
        alterados = 0
        for equivalente in self.equivalentes(candidato_id):
            if equivalente.status != status:
                equivalente.status = status
                equivalente.requer_revisao = False
                alterados += 1
        return alterados

    def confirmar_automaticos(self, limiar: float) -> int:
        """Confirma em lote as ocorrências de alta confiança que não exigem revisão."""
        confirmados = 0
        for candidato in self.candidatos:
            if (
                candidato.status == Status.DETECTADO
                and not candidato.requer_revisao
                and candidato.confianca >= limiar
                and candidato.bboxes
            ):
                candidato.status = Status.CONFIRMADO
                confirmados += 1
        return confirmados

    def adicionar_manual(
        self,
        documento: str,
        pagina: int,
        categoria: Categoria,
        valor: str,
        bboxes: list | None = None,
    ) -> Candidato:
        """Inclui uma ocorrência indicada manualmente pelo usuário."""
        candidato = Candidato(
            documento=documento,
            pagina=pagina,
            categoria=categoria,
            valor=valor,
            origem=Origem.MANUAL,
            status=Status.CONFIRMADO,
            confianca=1.0,
            bboxes=list(bboxes or []),
            detector="manual",
            motivo="Ocorrência indicada manualmente na revisão",
        )
        self.candidatos.append(candidato)
        self._por_id[candidato.id] = candidato
        self.atribuir_pseudonimos()
        return candidato

    # ------------------------------------------------------------- consultas
    def por_documento(self, documento: str) -> list[Candidato]:
        return [c for c in self.candidatos if c.documento == documento]

    def confirmados(self, documento: str | None = None) -> list[Candidato]:
        base = self.por_documento(documento) if documento else self.candidatos
        return [c for c in base if c.status == Status.CONFIRMADO]

    def pendentes(self, documento: str | None = None) -> list[Candidato]:
        base = self.por_documento(documento) if documento else self.candidatos
        return [
            c
            for c in base
            if c.status in (Status.PENDENTE, Status.DETECTADO) or c.requer_revisao
        ]

    def rejeitados(self, documento: str | None = None) -> list[Candidato]:
        base = self.por_documento(documento) if documento else self.candidatos
        return [c for c in base if c.status == Status.REJEITADO]

    def falhas(self, documento: str | None = None) -> list[Candidato]:
        base = self.por_documento(documento) if documento else self.candidatos
        return [c for c in base if c.status == Status.FALHA_CRITICA]

    def valores_confirmados(self, documento: str | None = None) -> set[str]:
        """Valores originais confirmados — usados apenas em memória na validação."""
        return {c.valor for c in self.confirmados(documento)}

    def contagem_por_categoria(self, documento: str | None = None) -> dict[str, int]:
        base = self.por_documento(documento) if documento else self.candidatos
        return dict(Counter(c.categoria.value for c in base))

    def contagem_por_status(self, documento: str | None = None) -> dict[str, int]:
        base = self.por_documento(documento) if documento else self.candidatos
        return dict(Counter(c.status.value for c in base))

    def resumo(self, documento: str | None = None) -> dict[str, object]:
        base = self.por_documento(documento) if documento else self.candidatos
        return {
            "total": len(base),
            "confirmados": len([c for c in base if c.status == Status.CONFIRMADO]),
            "rejeitados": len([c for c in base if c.status == Status.REJEITADO]),
            "pendentes": len(self.pendentes(documento)),
            "redigidos": len([c for c in base if c.status == Status.REDIGIDO]),
            "verificados": len([c for c in base if c.status == Status.VERIFICADO]),
            "falhas": len([c for c in base if c.status == Status.FALHA_CRITICA]),
            "por_categoria": self.contagem_por_categoria(documento),
            "entidades": len({c.entidade_id for c in base if c.entidade_id}),
        }

    def tabela_reversao(self, autorizado: bool) -> dict[str, list[str]]:
        """Mapa pseudônimo → valores originais.

        Só é produzido mediante autorização explícita do usuário. Por padrão o
        aplicativo não gera nem grava esta tabela.
        """
        if not autorizado:
            return {}
        return {e.pseudonimo: sorted(e.valores) for e in self.entidades.values()}

    def limpar(self) -> None:
        """Descarta todos os valores originais mantidos em memória."""
        self.candidatos.clear()
        self.entidades.clear()
        self._por_id.clear()
        self._contadores.clear()
