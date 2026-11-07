"""Testes da detecção de dados pessoais (itens 6, 7, 8, 9 e 18 dos testes obrigatórios)."""

from __future__ import annotations

import pytest

from anonimizador_dpu.core.config import Config
from anonimizador_dpu.core.entity_detector import detectar
from anonimizador_dpu.core.models import Categoria, Papel


def categorias(texto: str, cfg: Config | None = None) -> set[Categoria]:
    return {a.categoria for a in detectar(texto, cfg or Config())}


def valores(texto: str, categoria: Categoria, cfg: Config | None = None) -> list[str]:
    return [a.valor for a in detectar(texto, cfg or Config()) if a.categoria == categoria]


class TestCPF:
    def test_com_e_sem_pontuacao(self):
        texto = "CPF formatado 529.982.247-25 e sem pontuacao 11144477735."
        encontrados = valores(texto, Categoria.CPF)
        assert "529.982.247-25" in encontrados
        assert "11144477735" in encontrados

    def test_cpf_invalido_com_rotulo_vira_pendencia(self):
        achados = [
            a
            for a in detectar("CPF 529.982.247-24", Config())
            if a.categoria == Categoria.CPF
        ]
        assert achados, "CPF rotulado com DV inválido deve ser sinalizado"
        assert achados[0].requer_revisao
        assert achados[0].confianca < 0.9

    def test_numero_qualquer_nao_vira_cpf(self):
        assert Categoria.CPF not in categorias("O valor de 2020 processos e 123456.")


class TestCNPJeCEP:
    def test_cnpj(self):
        assert "11.222.333/0001-81" in valores(
            "Inscrita no CNPJ 11.222.333/0001-81.", Categoria.CNPJ, _cfg_cnpj()
        )

    def test_cep_com_hifen_e_com_rotulo(self):
        assert "70040-010" in valores("CEP 70040-010", Categoria.CEP)
        assert "70040-010" in valores("Endereco qualquer, 70040-010.", Categoria.CEP)

    def test_oito_digitos_sem_contexto_nao_vira_cep(self):
        assert Categoria.CEP not in categorias("Protocolo 70040010 registrado.")


class TestProcesso:
    def test_padrao_cnj(self):
        achados = detectar("Processo n. 0000001-78.2020.8.26.0100", Config())
        cnj = [a for a in achados if a.categoria == Categoria.PROCESSO_CNJ]
        assert cnj and cnj[0].confianca >= 0.95

    def test_cnj_com_dv_invalido_requer_revisao(self):
        achados = [
            a
            for a in detectar("Processo 0000001-79.2020.8.26.0100", Config())
            if a.categoria == Categoria.PROCESSO_CNJ
        ]
        assert achados and achados[0].requer_revisao


class TestDadosBancarios:
    def test_tabela_bancaria(self):
        texto = (
            "Banco: 001   Agencia: 1234   Conta corrente: 12345-6\n"
            "Chave Pix: 3f2504e0-4f89-11d3-9a0c-0305e82c3301\n"
            "Cartao: 4539 5787 6362 1486"
        )
        achadas = categorias(texto)
        assert Categoria.AGENCIA_BANCARIA in achadas
        assert Categoria.CONTA_BANCARIA in achadas
        assert Categoria.CHAVE_PIX in achadas
        assert Categoria.CARTAO in achadas


class TestNomes:
    def test_nome_com_rotulo_processual_tem_papel(self):
        achados = [
            a
            for a in detectar("Requerente: Pessoa Teste Alfa, brasileira.", Config())
            if a.categoria == Categoria.NOME_PESSOA
        ]
        assert achados
        assert achados[0].papel == Papel.REQUERENTE
        assert achados[0].confianca >= 0.85

    def test_profissionais_dependem_da_politica(self):
        texto = "Advogado: Pessoa Teste Delta, OAB/DF 1234."
        assert Categoria.NOME_PESSOA not in categorias(texto)

        cfg = Config()
        cfg.deteccao.anonimizar_profissionais = True
        assert Categoria.NOME_PESSOA in categorias(texto, cfg)

    def test_nome_isolado_de_um_token_nao_e_detectado(self):
        assert Categoria.NOME_PESSOA not in categorias("Compareceu Alfa.")


class TestFalsosPositivos:
    """Item 18: texto jurídico sem dados pessoais não deve gerar ocorrências."""

    TEXTO = (
        "O Supremo Tribunal Federal firmou entendimento no Tema 1007.\n"
        "A Defensoria Publica da Uniao atua nos termos da Lei Complementar 80.\n"
        "O Instituto Nacional do Seguro Social indeferiu o requerimento.\n"
        "Aplica-se o artigo 203 da Constituicao Federal de 1988.\n"
        "O Tribunal Regional Federal da 1a Regiao negou provimento.\n"
        "Sao Paulo, Minas Gerais e Rio de Janeiro sao unidades federativas.\n"
        "Lei n. 8.213/1991 e Decreto n. 3.048/1999 regem a materia.\n"
    )

    def test_sem_ocorrencias(self):
        achados = detectar(self.TEXTO, Config())
        assert achados == [], f"Falsos positivos: {[(a.categoria.value, a.valor) for a in achados]}"


class TestContencao:
    def test_cep_dentro_do_endereco_mantem_ambos(self):
        texto = "Reside na Rua das Flores, 123, Bairro Centro, CEP 70040-010."
        achadas = categorias(texto)
        assert Categoria.ENDERECO in achadas
        assert Categoria.CEP in achadas

    def test_logradouro_nao_vira_nome_de_pessoa(self):
        texto = "Reside na Rua das Flores, 123, Bairro Centro."
        assert Categoria.NOME_PESSOA not in categorias(texto)


class TestCategoriasDesativadas:
    def test_categoria_desativada_nao_gera_ocorrencia(self):
        cfg = Config()
        cfg.ativar(Categoria.EMAIL, False)
        assert Categoria.EMAIL not in categorias("Contato: alguem@exemplo.invalido", cfg)


class TestTermosPersonalizados:
    def test_termo_configurado_e_detectado(self):
        cfg = Config()
        cfg.deteccao.termos_personalizados = ["Projeto Sigiloso X"]
        achados = detectar("Documento do Projeto Sigiloso X em anexo.", cfg)
        assert any(a.detector == "termo_personalizado" for a in achados)

    def test_termo_ignorado_nao_e_detectado(self):
        cfg = Config()
        cfg.deteccao.termos_ignorados = ["Pessoa Teste Alfa"]
        assert Categoria.NOME_PESSOA not in categorias(
            "Requerente: Pessoa Teste Alfa.", cfg
        )


class TestSaudeEOutros:
    def test_cid_com_rotulo(self):
        assert Categoria.DADO_SAUDE in categorias("Diagnostico CID F32.1 confirmado.")

    def test_cid_sem_rotulo_nao_detectado(self):
        assert Categoria.DADO_SAUDE not in categorias("O item F32 do edital.")

    def test_url_com_token(self):
        assert Categoria.URL_COM_TOKEN in categorias(
            "Acesse https://exemplo.invalido/consulta?token=abc123"
        )

    def test_data_de_nascimento_exige_contexto(self):
        assert Categoria.DATA_NASCIMENTO in categorias("Nascida em 12/03/1980.")
        assert Categoria.DATA_NASCIMENTO not in categorias("Protocolado em 12/03/1980.")


def _cfg_cnpj() -> Config:
    cfg = Config()
    cfg.ativar(Categoria.CNPJ, True)
    return cfg


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   ",
        "\n\n",
    ],
)
def test_texto_vazio(texto):
    assert detectar(texto, Config()) == []
