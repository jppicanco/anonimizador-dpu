"""Testes das proteções de segurança (itens 25 e 26 dos testes obrigatórios)."""

from __future__ import annotations

import socket
import urllib.request

import pytest

from anonimizador_dpu.core.security import (
    AcessoRedeBloqueado,
    ErroSeguranca,
    LimiteExcedido,
    caminho_seguro,
    copia_de_trabalho,
    destino_seguro,
    destino_sem_colisao,
    rede_bloqueada,
    sha256_arquivo,
    validar_pdf_entrada,
)


class TestBloqueioDeRede:
    """Item 26 — o processamento não depende nem utiliza conexão externa."""

    def test_socket_bloqueado_no_contexto(self):
        with rede_bloqueada():
            with pytest.raises(AcessoRedeBloqueado):
                socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def test_urllib_bloqueado(self):
        with rede_bloqueada():
            with pytest.raises(Exception) as erro:
                urllib.request.urlopen("http://localhost:9/", timeout=1)
            assert "rede" in str(erro.value).lower() or isinstance(
                erro.value, AcessoRedeBloqueado
            )

    def test_rede_restaurada_apos_o_contexto(self):
        with rede_bloqueada():
            pass
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()

    def test_rede_restaurada_mesmo_com_excecao(self):
        with pytest.raises(ValueError):
            with rede_bloqueada():
                raise ValueError("falha simulada")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.close()


class TestCaminhos:
    def test_recusa_caminho_vazio(self):
        with pytest.raises(ErroSeguranca):
            caminho_seguro("")

    def test_recusa_caractere_nulo(self):
        with pytest.raises(ErroSeguranca):
            caminho_seguro("arquivo\x00.pdf")

    def test_recusa_extensao_diferente(self, tmp_path):
        arquivo = tmp_path / "documento.txt"
        arquivo.write_text("conteúdo", encoding="utf-8")
        with pytest.raises(ErroSeguranca):
            validar_pdf_entrada(arquivo)

    def test_recusa_arquivo_sem_assinatura_pdf(self, tmp_path):
        arquivo = tmp_path / "falso.pdf"
        arquivo.write_bytes(b"isto nao e um PDF")
        with pytest.raises(ErroSeguranca):
            validar_pdf_entrada(arquivo)

    def test_limite_de_tamanho(self, pasta_fixtures):
        with pytest.raises(LimiteExcedido):
            validar_pdf_entrada(pasta_fixtures / "02_digitalizado.pdf", max_mb=0)


class TestProtecaoDoOriginal:
    """Item 25 — tentativa de sobrescrever o original é bloqueada."""

    def test_destino_na_mesma_pasta_nao_coincide_com_original(self, pasta_fixtures):
        entrada = pasta_fixtures / "01_texto_cpf.pdf"
        destino = destino_seguro(entrada, entrada.parent, "_ANONIMIZADO")
        assert destino != entrada
        assert destino.name == "01_texto_cpf_ANONIMIZADO.pdf"

    def test_sufixo_vazio_na_mesma_pasta_e_recusado(self, pasta_fixtures):
        entrada = pasta_fixtures / "01_texto_cpf.pdf"
        with pytest.raises(ErroSeguranca):
            destino_seguro(entrada, entrada.parent, "")

    def test_colisao_gera_nome_alternativo(self, tmp_path):
        existente = tmp_path / "saida.pdf"
        existente.write_bytes(b"%PDF-1.7\n")
        alternativo = destino_sem_colisao(existente)
        assert alternativo != existente
        assert not alternativo.exists()

    def test_copia_de_trabalho_preserva_o_original(self, pasta_fixtures):
        entrada = pasta_fixtures / "01_texto_cpf.pdf"
        antes = sha256_arquivo(entrada)
        with copia_de_trabalho(entrada) as copia:
            assert copia != entrada
            copia.write_bytes(b"%PDF-1.7\nalterado")
        assert sha256_arquivo(entrada) == antes


def test_hash_estavel(pasta_fixtures):
    entrada = pasta_fixtures / "01_texto_cpf.pdf"
    assert sha256_arquivo(entrada) == sha256_arquivo(entrada)
    assert len(sha256_arquivo(entrada)) == 64
