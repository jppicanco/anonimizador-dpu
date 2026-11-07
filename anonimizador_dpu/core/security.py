"""Mecanismos de segurança operacional do aplicativo.

Inclui:
  * bloqueio efetivo de rede durante o processamento documental;
  * validação de caminhos de arquivo;
  * verificação de limites (tamanho, páginas, tempo);
  * diretório temporário com permissões restritas e limpeza garantida;
  * cálculo de hash do arquivo de saída.
"""

from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import socket
import stat
import tempfile
import time
from pathlib import Path
from typing import Iterator

from .models import Risco, Severidade


class ErroSeguranca(Exception):
    """Violação de uma regra de segurança do aplicativo."""


class AcessoRedeBloqueado(ErroSeguranca):
    """Tentativa de acesso à rede durante o processamento documental."""


class LimiteExcedido(ErroSeguranca):
    """Documento excede um limite configurado de tamanho, páginas ou tempo."""


# ----------------------------------------------------------------- rede
class _SocketBloqueado(socket.socket):
    def __init__(self, *args, **kwargs):  # noqa: D401 - bloqueio incondicional
        raise AcessoRedeBloqueado(
            "Acesso à rede bloqueado durante o processamento documental."
        )


@contextlib.contextmanager
def rede_bloqueada() -> Iterator[None]:
    """Bloqueia a criação de sockets no processo enquanto o bloco executa.

    Garantia verificável: qualquer tentativa de conexão (biblioteca própria ou
    de terceiros) levanta :class:`AcessoRedeBloqueado`. O bloqueio é restaurado
    ao final, inclusive em caso de exceção.
    """
    original_socket = socket.socket
    original_create = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    def _create_bloqueado(*args, **kwargs):
        raise AcessoRedeBloqueado(
            "Acesso à rede bloqueado durante o processamento documental."
        )

    socket.socket = _SocketBloqueado  # type: ignore[assignment]
    socket.create_connection = _create_bloqueado  # type: ignore[assignment]
    socket.getaddrinfo = _create_bloqueado  # type: ignore[assignment]
    try:
        yield
    finally:
        socket.socket = original_socket  # type: ignore[assignment]
        socket.create_connection = original_create  # type: ignore[assignment]
        socket.getaddrinfo = original_getaddrinfo  # type: ignore[assignment]


# ------------------------------------------------------------- caminhos
_EXTENSOES_PERMITIDAS = {".pdf"}


def caminho_seguro(caminho: str | os.PathLike, deve_existir: bool = True) -> Path:
    """Normaliza e valida um caminho de arquivo informado pelo usuário."""
    if caminho is None or str(caminho).strip() == "":
        raise ErroSeguranca("Caminho de arquivo vazio.")
    texto = str(caminho)
    if "\x00" in texto:
        raise ErroSeguranca("Caminho de arquivo inválido (caractere nulo).")
    p = Path(texto).expanduser()
    try:
        p = p.resolve(strict=deve_existir)
    except (OSError, RuntimeError) as exc:
        raise ErroSeguranca(f"Caminho inacessível: {exc}") from exc
    if deve_existir:
        if not p.is_file():
            raise ErroSeguranca("O caminho informado não é um arquivo regular.")
        if p.is_symlink():
            raise ErroSeguranca("Links simbólicos não são aceitos como entrada.")
    return p


def validar_pdf_entrada(caminho: str | os.PathLike, max_mb: int = 500) -> Path:
    """Valida um PDF de entrada: existência, extensão, assinatura e tamanho."""
    p = caminho_seguro(caminho, deve_existir=True)
    if p.suffix.lower() not in _EXTENSOES_PERMITIDAS:
        raise ErroSeguranca(f"Extensão não suportada: {p.suffix!r} (esperado .pdf).")
    tamanho = p.stat().st_size
    if tamanho == 0:
        raise ErroSeguranca("Arquivo vazio.")
    if tamanho > max_mb * 1024 * 1024:
        raise LimiteExcedido(
            f"Arquivo com {tamanho / 1048576:.1f} MB excede o limite de {max_mb} MB."
        )
    with open(p, "rb") as fh:
        cabecalho = fh.read(1024)
    if b"%PDF" not in cabecalho:
        raise ErroSeguranca("O arquivo não possui assinatura de PDF (%PDF).")
    return p


def destino_seguro(
    entrada: Path, pasta_saida: str | os.PathLike, sufixo: str = "_ANONIMIZADO"
) -> Path:
    """Monta o caminho de saída garantindo que o original nunca seja sobrescrito."""
    pasta = Path(pasta_saida).expanduser().resolve()
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{entrada.stem}{sufixo}.pdf"
    if destino.resolve() == entrada.resolve():
        raise ErroSeguranca(
            "O arquivo de saída coincide com o original. O original nunca é sobrescrito."
        )
    return destino


def destino_sem_colisao(destino: Path) -> Path:
    """Gera um nome alternativo quando já existe arquivo com o mesmo nome."""
    if not destino.exists():
        return destino
    base, sufixo = destino.stem, destino.suffix
    for i in range(1, 1000):
        alternativo = destino.with_name(f"{base}_{i:03d}{sufixo}")
        if not alternativo.exists():
            return alternativo
    raise ErroSeguranca("Não foi possível gerar nome de saída sem colisão.")


# ------------------------------------------------------------ temporários
class DiretorioTemporarioSeguro:
    """Diretório temporário com permissões restritas e limpeza ao final.

    Observação de segurança documentada ao usuário: a exclusão lógica dos
    arquivos temporários NÃO garante eliminação física irrecuperável em SSD.
    """

    def __init__(self, prefixo: str = "anonimizador_dpu_") -> None:
        self.caminho = Path(tempfile.mkdtemp(prefix=prefixo))
        try:
            os.chmod(self.caminho, stat.S_IRWXU)  # 0o700
        except OSError:
            pass

    def __enter__(self) -> Path:
        return self.caminho

    def __exit__(self, *exc) -> None:
        self.limpar()

    def limpar(self) -> None:
        shutil.rmtree(self.caminho, ignore_errors=True)


@contextlib.contextmanager
def copia_de_trabalho(entrada: Path) -> Iterator[Path]:
    """Cria uma cópia de trabalho do PDF; o original nunca é aberto para escrita."""
    with DiretorioTemporarioSeguro() as tmp:
        copia = tmp / entrada.name
        shutil.copy2(entrada, copia)
        try:
            os.chmod(copia, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass
        yield copia


# ----------------------------------------------------------------- hash
def sha256_arquivo(caminho: str | os.PathLike) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        for bloco in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


# ---------------------------------------------------------------- limites
class ControleTempo:
    """Controla o tempo máximo de processamento de um documento."""

    def __init__(self, timeout_s: int) -> None:
        self.timeout_s = timeout_s
        self.inicio = time.monotonic()

    @property
    def decorrido(self) -> float:
        return time.monotonic() - self.inicio

    def expirado(self) -> bool:
        return self.timeout_s > 0 and self.decorrido > self.timeout_s

    def verificar(self) -> None:
        if self.expirado():
            raise LimiteExcedido(
                f"Tempo máximo de processamento excedido ({self.timeout_s} s)."
            )


def risco_de_excecao(exc: BaseException, codigo: str, pagina: int | None = None) -> Risco:
    """Converte uma exceção em um risco registrável, sem vazar conteúdo do documento."""
    return Risco(
        codigo=codigo,
        descricao=f"{type(exc).__name__}: {exc}"[:300],
        severidade=Severidade.CRITICO,
        pagina=pagina,
        bloqueia_aprovacao=True,
    )
