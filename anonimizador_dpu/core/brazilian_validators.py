"""Validadores determinísticos de identificadores brasileiros.

Importante: a validação matemática de um identificador (dígitos verificadores)
NÃO prova que ele pertence a uma pessoa real, nem que o número no documento é
verdadeiro. Ela serve apenas para elevar ou reduzir a confiança de uma detecção.
"""

from __future__ import annotations

import re

__all__ = [
    "somente_digitos",
    "validar_cpf",
    "validar_cnpj",
    "validar_cep",
    "validar_telefone",
    "validar_cnj",
    "validar_pis_pasep",
    "validar_titulo_eleitor",
    "validar_cnh",
    "validar_cartao_luhn",
    "validar_placa",
    "validar_nb",
    "formatar_cpf",
]

#: DDDs efetivamente atribuídos no Brasil (Plano Nacional de Numeração).
DDDS_VALIDOS = frozenset(
    {
        11, 12, 13, 14, 15, 16, 17, 18, 19,
        21, 22, 24, 27, 28,
        31, 32, 33, 34, 35, 37, 38,
        41, 42, 43, 44, 45, 46, 47, 48, 49,
        51, 53, 54, 55,
        61, 62, 63, 64, 65, 66, 67, 68, 69,
        71, 73, 74, 75, 77, 79,
        81, 82, 83, 84, 85, 86, 87, 88, 89,
        91, 92, 93, 94, 95, 96, 97, 98, 99,
    }
)

#: Segmentos do Poder Judiciário (dígito "J" do número CNJ).
SEGMENTOS_CNJ = frozenset({1, 2, 3, 4, 5, 6, 7, 8, 9})


def somente_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


# --------------------------------------------------------------------- CPF
def validar_cpf(valor: str) -> bool:
    """Valida os dois dígitos verificadores do CPF.

    Rejeita sequências de dígitos repetidos (111.111.111-11 etc.), que passam
    no cálculo mas nunca correspondem a CPF válido emitido.
    """
    numero = somente_digitos(valor)
    if len(numero) != 11 or numero == numero[0] * 11:
        return False
    digitos = [int(d) for d in numero]
    for posicao in (9, 10):
        peso_inicial = posicao + 1
        soma = sum(digitos[i] * (peso_inicial - i) for i in range(posicao))
        resto = (soma * 10) % 11
        esperado = 0 if resto == 10 else resto
        if digitos[posicao] != esperado:
            return False
    return True


def formatar_cpf(valor: str) -> str:
    n = somente_digitos(valor)
    if len(n) != 11:
        return valor
    return f"{n[:3]}.{n[3:6]}.{n[6:9]}-{n[9:]}"


# -------------------------------------------------------------------- CNPJ
def validar_cnpj(valor: str) -> bool:
    """Valida os dígitos verificadores do CNPJ numérico (14 dígitos)."""
    numero = somente_digitos(valor)
    if len(numero) != 14 or numero == numero[0] * 14:
        return False
    digitos = [int(d) for d in numero]
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6] + pesos_1
    for pesos, posicao in ((pesos_1, 12), (pesos_2, 13)):
        soma = sum(d * p for d, p in zip(digitos[:posicao], pesos))
        resto = soma % 11
        esperado = 0 if resto < 2 else 11 - resto
        if digitos[posicao] != esperado:
            return False
    return True


# --------------------------------------------------------------------- CEP
def validar_cep(valor: str) -> bool:
    """Verifica apenas a forma do CEP: oito dígitos, não todos iguais.

    Não há dígito verificador em CEP; a validade real depende de base de dados
    dos Correios, que não é consultada (o aplicativo é offline).
    """
    numero = somente_digitos(valor)
    return len(numero) == 8 and numero != numero[0] * 8 and not numero.startswith("0000")


# ---------------------------------------------------------------- telefone
def validar_telefone(valor: str) -> bool:
    """Valida telefone brasileiro com DDD atribuído (10 ou 11 dígitos)."""
    numero = somente_digitos(valor)
    if numero.startswith("55") and len(numero) in (12, 13):
        numero = numero[2:]
    if len(numero) not in (10, 11):
        return False
    ddd = int(numero[:2])
    if ddd not in DDDS_VALIDOS:
        return False
    assinante = numero[2:]
    if len(assinante) == 9:
        return assinante[0] == "9"
    return assinante[0] in "2345"


# --------------------------------------------------------------- processo
def validar_cnj(valor: str) -> bool:
    """Valida o dígito verificador do número único CNJ (Resolução CNJ 65/2008).

    Formato: NNNNNNN-DD.AAAA.J.TR.OOOO, verificação por módulo 97 base 10.
    """
    numero = somente_digitos(valor)
    if len(numero) != 20:
        return False
    sequencial, dv, ano, segmento, tribunal, origem = (
        numero[0:7],
        numero[7:9],
        numero[9:13],
        numero[13:14],
        numero[14:16],
        numero[16:20],
    )
    if int(segmento) not in SEGMENTOS_CNJ:
        return False
    if not (1900 <= int(ano) <= 2200):
        return False
    base = int(sequencial + ano + segmento + tribunal + origem)
    return int(dv) == 98 - (base * 100) % 97


# ------------------------------------------------------------ PIS / PASEP
def validar_pis_pasep(valor: str) -> bool:
    """Valida o dígito verificador de PIS/PASEP/NIT (11 dígitos)."""
    numero = somente_digitos(valor)
    if len(numero) != 11 or numero == numero[0] * 11:
        return False
    pesos = [3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma = sum(int(d) * p for d, p in zip(numero[:10], pesos))
    resto = soma % 11
    esperado = 0 if resto < 2 else 11 - resto
    return int(numero[10]) == esperado


# --------------------------------------------------------- título eleitor
def validar_titulo_eleitor(valor: str) -> bool:
    """Valida os dois dígitos verificadores do título de eleitor (12 dígitos)."""
    numero = somente_digitos(valor)
    if len(numero) != 12 or numero == numero[0] * 12:
        return False
    sequencial, uf, dvs = numero[:8], numero[8:10], numero[10:]
    if not (1 <= int(uf) <= 28):
        return False
    soma = sum(int(d) * p for d, p in zip(sequencial, range(2, 10)))
    dv1 = soma % 11
    if dv1 == 10:
        dv1 = 0 if uf not in ("01", "02") else 1
    soma2 = int(uf[0]) * 7 + int(uf[1]) * 8 + dv1 * 9
    dv2 = soma2 % 11
    if dv2 == 10:
        dv2 = 0 if uf not in ("01", "02") else 1
    return dvs == f"{dv1}{dv2}"


# --------------------------------------------------------------------- CNH
def validar_cnh(valor: str) -> bool:
    """Valida o número de registro da CNH (11 dígitos)."""
    numero = somente_digitos(valor)
    if len(numero) != 11 or numero == numero[0] * 11:
        return False
    soma = sum(int(numero[i]) * (9 - i) for i in range(9))
    dv1 = soma % 11
    acrescimo = 0
    if dv1 >= 10:
        dv1, acrescimo = 0, 2
    soma2 = sum(int(numero[i]) * (1 + i) for i in range(9))
    dv2 = soma2 % 11
    dv2 = 0 if dv2 >= 10 else dv2 - acrescimo
    if dv2 < 0:
        dv2 += 11
    return numero[9:] == f"{dv1}{dv2}"


# ------------------------------------------------------------------ cartão
def validar_cartao_luhn(valor: str) -> bool:
    """Valida número de cartão pelo algoritmo de Luhn (13 a 19 dígitos)."""
    numero = somente_digitos(valor)
    if not 13 <= len(numero) <= 19:
        return False
    soma, dobra = 0, False
    for ch in reversed(numero):
        d = int(ch)
        if dobra:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
        dobra = not dobra
    return soma % 10 == 0


# ------------------------------------------------------------------- placa
_PLACA_ANTIGA = re.compile(r"^[A-Z]{3}-?\d{4}$")
_PLACA_MERCOSUL = re.compile(r"^[A-Z]{3}\d[A-Z]\d{2}$")


def validar_placa(valor: str) -> bool:
    """Reconhece placas no padrão antigo (AAA-0000) e Mercosul (AAA0A00)."""
    texto = (valor or "").upper().replace(" ", "")
    return bool(_PLACA_ANTIGA.match(texto) or _PLACA_MERCOSUL.match(texto))


# -------------------------------------------------------- benefício (NB)
def validar_nb(valor: str) -> bool:
    """Verifica a forma de um número de benefício do INSS (NB).

    O NB tem 10 dígitos, sendo o último um dígito verificador calculado por
    módulo 11 sobre os nove primeiros. Nem todo número de 10 dígitos próximo da
    palavra "benefício" é um NB: a validação reduz, mas não elimina, falsos
    positivos.
    """
    numero = somente_digitos(valor)
    if len(numero) != 10 or numero == numero[0] * 10:
        return False
    pesos = [2, 3, 4, 5, 6, 7, 8, 9, 10]
    soma = sum(int(d) * p for d, p in zip(reversed(numero[:9]), pesos))
    resto = soma % 11
    esperado = 0 if resto in (0, 1) else 11 - resto
    if esperado == 10:
        esperado = 0
    return int(numero[9]) == esperado
