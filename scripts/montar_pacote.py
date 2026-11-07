"""Monta o pacote de distribuição do Anonimizador DPU.

Produz uma pasta autocontida e o ZIP correspondente, com:

* o executável gerado pelo PyInstaller;
* o Tesseract OCR embutido (licença Apache-2.0, redistribuição permitida),
  apenas com os idiomas necessários;
* a documentação, as licenças e o código-fonte.

O código-fonte vai junto por duas razões: o PyMuPDF é AGPL-3.0, e porque uma
ferramenta de anonimização que ninguém pode auditar não deveria ser usada.

Uso, a partir da raiz do projeto:

    python -m PyInstaller scripts/anonimizador_dpu.spec --noconfirm
    python scripts/montar_pacote.py
"""

from __future__ import annotations

import os
import shutil
import stat
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIST = RAIZ / "dist"
APP = DIST / "AnonimizadorDPU"
PACOTE = DIST / "AnonimizadorDPU_pacote"

#: Nome da pasta que o destinatário vê ao descompactar. O nome interno da
#: pasta de montagem não serve: ninguém quer extrair "AnonimizadorDPU_pacote".
RAIZ_NO_ZIP = "AnonimizadorDPU"

#: Idiomas do OCR que o pacote leva. Os demais só aumentariam o tamanho.
IDIOMAS = ("por.traineddata", "eng.traineddata", "osd.traineddata")

#: Documentação copiada para dentro do pacote.
DOCUMENTOS = (
    "README.md",
    "docs/MANUAL_USUARIO.md",
    "docs/LIMITACOES.md",
    "docs/SEGURANCA.md",
    "docs/ARQUITETURA.md",
    "docs/TESTES.md",
)

#: Código-fonte redistribuído (AGPL-3.0 do PyMuPDF).
FONTES = ("anonimizador_dpu", "tests", "scripts", "docs")
ARQUIVOS_FONTE = (
    "README.md",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
)


def localizar_tesseract() -> Path | None:
    candidatos = [
        Path(r"C:\Program Files\Tesseract-OCR"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR"),
    ]
    for c in candidatos:
        if (c / "tesseract.exe").exists():
            return c
    return None


def copiar_tesseract(destino: Path) -> bool:
    origem = localizar_tesseract()
    if origem is None:
        print("AVISO: Tesseract não encontrado; o pacote sairá sem OCR embutido.")
        return False
    alvo = destino / "tesseract"
    alvo.mkdir(parents=True, exist_ok=True)
    for item in origem.iterdir():
        if item.is_file():
            shutil.copy2(item, alvo / item.name)
    tessdata = alvo / "tessdata"
    tessdata.mkdir(exist_ok=True)
    for idioma in IDIOMAS:
        fonte = origem / "tessdata" / idioma
        if fonte.exists():
            shutil.copy2(fonte, tessdata / idioma)
        else:
            print(f"AVISO: idioma ausente: {idioma}")
    # Configuração auxiliar que o Tesseract procura em tessdata/configs.
    configs = origem / "tessdata" / "configs"
    if configs.is_dir():
        shutil.copytree(configs, tessdata / "configs", dirs_exist_ok=True)
    return True


def copiar_codigo_fonte(destino: Path) -> None:
    alvo = destino / "codigo-fonte"
    alvo.mkdir(parents=True, exist_ok=True)
    for pasta in FONTES:
        origem = RAIZ / pasta
        if origem.is_dir():
            shutil.copytree(
                origem,
                alvo / pasta,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
            )
    for arquivo in ARQUIVOS_FONTE:
        origem = RAIZ / arquivo
        if origem.exists():
            shutil.copy2(origem, alvo / Path(arquivo).name)


def copiar_documentacao(destino: Path) -> None:
    alvo = destino / "documentacao"
    alvo.mkdir(parents=True, exist_ok=True)
    for doc in DOCUMENTOS:
        origem = RAIZ / doc
        if origem.exists():
            shutil.copy2(origem, alvo / Path(doc).name)


def tamanho_mb(caminho: Path) -> float:
    if caminho.is_file():
        return caminho.stat().st_size / (1024 * 1024)
    total = sum(p.stat().st_size for p in caminho.rglob("*") if p.is_file())
    return total / (1024 * 1024)


def _forcar_remocao(func, caminho, excecao) -> None:
    """Retira o atributo somente-leitura e tenta de novo.

    O Tesseract traz arquivos marcados como somente-leitura, e o Windows
    recusa a remoção da pasta que os contém.
    """
    os.chmod(caminho, stat.S_IWRITE)
    func(caminho)


def main() -> int:
    if not (APP / "AnonimizadorDPU.exe").exists():
        print(
            "Executável não encontrado. Gere-o antes:\n"
            "    python -m PyInstaller scripts/anonimizador_dpu.spec --noconfirm"
        )
        return 1

    if PACOTE.exists():
        shutil.rmtree(PACOTE, onexc=_forcar_remocao)
    PACOTE.mkdir(parents=True)

    print("copiando aplicativo…")
    shutil.copytree(APP, PACOTE / "aplicativo")

    print("copiando Tesseract…")
    com_ocr = copiar_tesseract(PACOTE / "aplicativo")

    print("copiando documentação…")
    copiar_documentacao(PACOTE)

    print("copiando código-fonte…")
    copiar_codigo_fonte(PACOTE)

    for extra in ("INSTALAR.txt", "LICENCAS.txt"):
        origem = RAIZ / "scripts" / "pacote" / extra
        if origem.exists():
            shutil.copy2(origem, PACOTE / extra)

    print(f"\npasta do pacote: {PACOTE} ({tamanho_mb(PACOTE):.0f} MB)")
    print(f"OCR embutido: {'sim' if com_ocr else 'NÃO'}")

    zip_destino = DIST / "AnonimizadorDPU.zip"
    if zip_destino.exists():
        zip_destino.unlink()
    print("\ncompactando…")
    with zipfile.ZipFile(zip_destino, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for arquivo in sorted(PACOTE.rglob("*")):
            if arquivo.is_file():
                interno = Path(RAIZ_NO_ZIP) / arquivo.relative_to(PACOTE)
                z.write(arquivo, interno)
    print(f"ZIP: {zip_destino} ({tamanho_mb(zip_destino):.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
