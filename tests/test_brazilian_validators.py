"""Testes dos validadores de identificadores brasileiros (exemplos positivos e negativos)."""

from __future__ import annotations

import pytest

from anonimizador_dpu.core.brazilian_validators import (
    somente_digitos,
    validar_cartao_luhn,
    validar_cep,
    validar_cnh,
    validar_cnj,
    validar_cnpj,
    validar_cpf,
    validar_nb,
    validar_pis_pasep,
    validar_placa,
    validar_telefone,
    validar_titulo_eleitor,
)


class TestCPF:
    @pytest.mark.parametrize(
        "valor",
        ["529.982.247-25", "52998224725", "529 982 247 25", "111.444.777-35"],
    )
    def test_validos_em_formatos_diferentes(self, valor):
        assert validar_cpf(valor)

    @pytest.mark.parametrize(
        "valor",
        [
            "529.982.247-24",  # dígito verificador alterado
            "111.111.111-11",  # sequência repetida
            "000.000.000-00",
            "1234567890",  # dígitos de menos
            "",
            "abc.def.ghi-jk",
        ],
    )
    def test_invalidos(self, valor):
        assert not validar_cpf(valor)


class TestCNPJ:
    def test_valido_com_e_sem_pontuacao(self):
        assert validar_cnpj("11.222.333/0001-81")
        assert validar_cnpj("11222333000181")

    @pytest.mark.parametrize("valor", ["11.222.333/0001-82", "11111111111111", "123"])
    def test_invalidos(self, valor):
        assert not validar_cnpj(valor)


class TestCEP:
    def test_formatos_aceitos(self):
        assert validar_cep("70040-010")
        assert validar_cep("70040010")

    @pytest.mark.parametrize("valor", ["00000000", "7004001", "abcdefgh"])
    def test_recusados(self, valor):
        assert not validar_cep(valor)


class TestTelefone:
    @pytest.mark.parametrize(
        "valor",
        ["(61) 99999-1234", "61999991234", "(11) 3333-4444", "+55 61 99999-1234"],
    )
    def test_validos(self, valor):
        assert validar_telefone(valor)

    @pytest.mark.parametrize(
        "valor",
        [
            "(00) 1111-1111",  # DDD inexistente
            "(61) 19999-1234",  # celular sem o 9 inicial
            "123456",
        ],
    )
    def test_invalidos(self, valor):
        assert not validar_telefone(valor)


class TestProcessoCNJ:
    def test_numero_valido(self):
        assert validar_cnj("0000001-78.2020.8.26.0100")
        assert validar_cnj("00000017820208260100")

    @pytest.mark.parametrize(
        "valor",
        [
            "0000001-79.2020.8.26.0100",  # DV incorreto
            "0000001-78.2020.0.26.0100",  # segmento inválido
            "123",
        ],
    )
    def test_invalidos(self, valor):
        assert not validar_cnj(valor)


class TestOutrosIdentificadores:
    def test_pis_pasep(self):
        assert validar_pis_pasep("12065537436")
        assert not validar_pis_pasep("12065537437")
        assert not validar_pis_pasep("11111111111")

    def test_titulo_eleitor(self):
        assert validar_titulo_eleitor("000123450159")
        assert not validar_titulo_eleitor("000123450158")

    def test_cnh(self):
        assert validar_cnh("01234567807")
        assert not validar_cnh("01234567808")

    def test_cartao_luhn(self):
        assert validar_cartao_luhn("4539 5787 6362 1486")
        assert not validar_cartao_luhn("4539 5787 6362 1487")

    def test_placa(self):
        assert validar_placa("ABC-1234")
        assert validar_placa("ABC1D23")
        assert not validar_placa("AB1234")

    def test_beneficio(self):
        assert validar_nb("1234567890")
        assert not validar_nb("1234567891")

    def test_somente_digitos(self):
        assert somente_digitos("529.982.247-25") == "52998224725"
        assert somente_digitos(None) == ""


def test_validacao_matematica_nao_prova_titularidade():
    """Documenta o limite: um CPF válido pode ser inteiramente fictício.

    O CPF usado nos testes passa na validação de dígitos e é deliberadamente
    fictício; a validação nunca é tratada como prova de que o número pertence a
    uma pessoa real.
    """
    assert validar_cpf("529.982.247-25")
