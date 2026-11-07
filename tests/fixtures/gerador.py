"""Geração de PDFs sintéticos para teste.

Todos os dados usados aqui são deliberadamente fictícios ("Pessoa Teste Alfa",
CPFs de teste) e não correspondem a pessoas reais. Processos judiciais reais
nunca são usados no desenvolvimento ou nos testes desta ferramenta.
"""

from __future__ import annotations

from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

# ------------------------------------------------------------- dados fictícios
CPF_ALFA = "529.982.247-25"          # CPF de teste, dígitos verificadores válidos
CPF_ALFA_SEM_PONTO = "52998224725"
CPF_BETA = "111.444.777-35"
CNPJ_TESTE = "11.222.333/0001-81"
CEP_TESTE = "70040-010"
PROCESSO_TESTE = "0000001-78.2020.8.26.0100"
TELEFONE_TESTE = "(61) 99999-1234"
EMAIL_TESTE = "pessoa.alfa@exemplo.invalido"
NOME_ALFA = "Pessoa Teste Alfa"
NOME_BETA = "Pessoa Teste Beta"
NOME_GAMA = "Pessoa Teste Gama"
ENDERECO_TESTE = "Rua das Flores, 123, Bairro Centro"
NB_TESTE = "1234567890"

LARGURA, ALTURA = 595, 842  # A4 em pontos


def _fonte(tamanho: int) -> ImageFont.FreeTypeFont:
    for caminho in (
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(caminho).exists():
            return ImageFont.truetype(caminho, tamanho)
    return ImageFont.load_default()


def imagem_com_texto(
    linhas: list[str], largura: int = 1240, altura: int = 1754, tamanho: int = 38
) -> Image.Image:
    """Cria uma imagem de documento digitalizado com o texto informado."""
    img = Image.new("RGB", (largura, altura), "white")
    draw = ImageDraw.Draw(img)
    fonte = _fonte(tamanho)
    y = 90
    for linha in linhas:
        draw.text((90, y), linha, fill="black", font=fonte)
        y += int(tamanho * 1.7)
    return img


def _inserir_imagem(page: fitz.Page, img: Image.Image, rect: fitz.Rect | None = None) -> None:
    import io

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    page.insert_image(rect or page.rect, stream=buffer.getvalue())


def _nova(doc: fitz.Document) -> fitz.Page:
    return doc.new_page(width=LARGURA, height=ALTURA)


def _escrever(page: fitz.Page, linhas: list[str], y: float = 80, corpo: float = 11) -> None:
    for i, linha in enumerate(linhas):
        page.insert_text((60, y + i * (corpo + 6)), linha, fontsize=corpo, fontname="helv")


# ---------------------------------------------------------------- fixtures
def pdf_texto_com_cpf(destino: Path) -> Path:
    """1 — PDF com texto selecionável contendo CPF e outros identificadores."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            "EXCELENTISSIMO SENHOR JUIZ FEDERAL",
            f"Processo n. {PROCESSO_TESTE}",
            "",
            f"Requerente: {NOME_ALFA}, brasileira, nascida em 12/03/1980,",
            f"inscrita no CPF sob o n. {CPF_ALFA}, RG 12.345.678 SSP/SP,",
            f"residente na {ENDERECO_TESTE}, CEP {CEP_TESTE},",
            f"telefone {TELEFONE_TESTE}, e-mail {EMAIL_TESTE}.",
            "",
            "Requerido: INSTITUTO NACIONAL DO SEGURO SOCIAL",
            f"CNPJ {CNPJ_TESTE}.",
            "",
            f"Trata-se de pedido de restabelecimento do beneficio NB {NB_TESTE},",
            "com fundamento no artigo 59 da Lei n. 8.213/1991.",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_digitalizado(destino: Path) -> Path:
    """2 — PDF digitalizado (apenas imagem) com CPF e endereço."""
    doc = fitz.open()
    page = _nova(doc)
    img = imagem_com_texto(
        [
            "DECLARACAO DE RESIDENCIA",
            "",
            f"Nome: {NOME_ALFA}",
            f"CPF: {CPF_ALFA}",
            f"Endereco: {ENDERECO_TESTE}",
            f"CEP: {CEP_TESTE}",
            f"Telefone: {TELEFONE_TESTE}",
        ]
    )
    _inserir_imagem(page, img)
    doc.save(destino)
    doc.close()
    return destino


def pdf_hibrido(destino: Path) -> Path:
    """3 — Página com texto selecionável e imagem digitalizada com outros dados."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            "ANEXO I - COMPROVANTE",
            f"Documento apresentado por {NOME_ALFA}.",
            f"Processo n. {PROCESSO_TESTE}",
        ],
    )
    img = imagem_com_texto(
        [f"CPF: {CPF_BETA}", f"Titular: {NOME_BETA}", f"CEP: {CEP_TESTE}"],
        largura=1000,
        altura=560,
        tamanho=44,
    )
    _inserir_imagem(page, img, fitz.Rect(60, 300, 535, 580))
    doc.save(destino)
    doc.close()
    return destino


def pdf_nome_repetido(destino: Path, paginas: int = 12) -> Path:
    """4 — Mesmo nome repetido em dezenas de ocorrências ao longo das páginas."""
    doc = fitz.open()
    for i in range(paginas):
        page = _nova(doc)
        _escrever(
            page,
            [
                f"Folha {i + 1}",
                f"A parte autora {NOME_ALFA} compareceu a audiencia.",
                f"Declarou {NOME_ALFA} que reside no endereco informado.",
                f"O depoimento de {NOME_ALFA} foi colhido em termo proprio.",
            ],
        )
    doc.save(destino)
    doc.close()
    return destino


def pdf_nomes_iguais(destino: Path) -> Path:
    """5 — Duas pessoas distintas com o mesmo nome, diferenciadas pelo CPF."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            "TERMO DE AUDIENCIA",
            f"Requerente: {NOME_ALFA}, CPF {CPF_ALFA}.",
            f"Testemunha: {NOME_ALFA}, CPF {CPF_BETA}, homonimo da parte autora.",
            "As duas pessoas sao distintas, conforme documentos apresentados.",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_cpf_formatos(destino: Path) -> Path:
    """6 — CPF com e sem pontuação, e CPF inválido rotulado."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            f"CPF formatado: {CPF_ALFA}",
            f"CPF sem pontuacao: {CPF_ALFA_SEM_PONTO}",
            f"CPF da testemunha: {CPF_BETA}",
            "CPF com digito invalido: 529.982.247-24",
            "Numero que nao e CPF: 123456 e 2020",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_cnpj_cep(destino: Path) -> Path:
    """7 — CNPJ e CEP em formatos variados."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            f"Empresa requerida inscrita no CNPJ {CNPJ_TESTE}.",
            "CNPJ sem pontuacao: 11222333000181",
            f"Endereco: {ENDERECO_TESTE}, CEP {CEP_TESTE}",
            "CEP sem hifen: 70040010",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_processo_cnj(destino: Path) -> Path:
    """8 — Número de processo no padrão CNJ, válido e inválido."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            f"Processo n. {PROCESSO_TESTE}",
            "Processo com digito incorreto: 0000001-79.2020.8.26.0100",
            "Autos n. 0000001-78.2020.8.26.0100 (repeticao)",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_dados_bancarios(destino: Path) -> Path:
    """9 — Dados bancários apresentados em tabela."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            "EXTRATO BANCARIO - DADOS DO TITULAR",
            f"Titular: {NOME_ALFA}",
            f"CPF: {CPF_ALFA}",
            "Banco: 001   Agencia: 1234   Conta corrente: 12345-6",
            "Chave Pix: 3f2504e0-4f89-11d3-9a0c-0305e82c3301",
            "Cartao: 4539 5787 6362 1486",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_nome_em_imagem(destino: Path) -> Path:
    """10 — Nome presente apenas dentro de uma imagem incorporada."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(page, ["Documento de identidade digitalizado:"])
    img = imagem_com_texto(
        ["CARTEIRA DE IDENTIDADE", f"Nome: {NOME_GAMA}", f"CPF: {CPF_ALFA}"],
        largura=1000,
        altura=520,
        tamanho=46,
    )
    _inserir_imagem(page, img, fitz.Rect(60, 150, 535, 400))
    doc.save(destino)
    doc.close()
    return destino


def pdf_cabecalho_rodape(destino: Path) -> Path:
    """11 — Dados pessoais em cabeçalho e rodapé de todas as páginas."""
    doc = fitz.open()
    for i in range(3):
        page = _nova(doc)
        page.insert_text(
            (60, 40), f"{NOME_ALFA} - CPF {CPF_ALFA}", fontsize=8, fontname="helv"
        )
        _escrever(page, [f"Conteudo da pagina {i + 1}.", "Texto do corpo do documento."], y=120)
        page.insert_text(
            (60, ALTURA - 40),
            f"Processo {PROCESSO_TESTE} - folha {i + 1}",
            fontsize=8,
            fontname="helv",
        )
    doc.save(destino)
    doc.close()
    return destino


def pdf_com_anotacao(destino: Path) -> Path:
    """12 — Dados pessoais dentro de anotação (comentário)."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(page, ["Peticao sem dados pessoais no corpo do texto."])
    annot = page.add_text_annot((300, 200), "Lembrete interno")
    annot.set_info(
        title=NOME_ALFA,
        content=f"Lembrete: CPF do assistido {CPF_ALFA}, contato {TELEFONE_TESTE}",
    )
    annot.update()
    doc.save(destino)
    doc.close()
    return destino


def pdf_metadados(destino: Path) -> Path:
    """13 — Metadados contendo nome fictício e identificadores."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(page, ["Documento com metadados preenchidos."])
    doc.set_metadata(
        {
            "title": f"Processo de {NOME_ALFA}",
            "author": NOME_ALFA,
            "subject": f"CPF {CPF_ALFA}",
            "keywords": f"{PROCESSO_TESTE}, {CEP_TESTE}",
            "creator": "Gerador de testes",
            "producer": "Gerador de testes",
        }
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_com_anexo(destino: Path) -> Path:
    """14 — PDF com arquivo incorporado de formato não suportado."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(page, ["Documento com arquivo incorporado."])
    doc.embfile_add(
        "planilha_teste.xlsx",
        b"conteudo binario ficticio de teste",
        filename="planilha_teste.xlsx",
        desc="Arquivo de teste nao suportado",
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_ilegivel_ocr(destino: Path) -> Path:
    """15 — Página cuja imagem é ilegível para OCR (ruído)."""
    import random

    random.seed(42)
    doc = fitz.open()
    page = _nova(doc)
    img = Image.new("RGB", (900, 1200), "white")
    pixels = img.load()
    for x in range(0, 900, 3):
        for y in range(0, 1200, 3):
            if random.random() < 0.5:
                pixels[x, y] = (random.randint(0, 120),) * 3
    _inserir_imagem(page, img)
    doc.save(destino)
    doc.close()
    return destino


def pdf_malformado(destino: Path) -> Path:
    """16 — Arquivo com cabeçalho de PDF, porém estrutura corrompida."""
    destino.write_bytes(
        b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"trailer\n<< /Root 1 0 R >>\n%%EOF\n"
    )
    return destino


def pdf_com_assinatura(destino: Path) -> Path:
    """17 — PDF com campo de assinatura digital."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(page, ["Documento com campo de assinatura."])
    widget = fitz.Widget()
    widget.field_name = "assinatura_teste"
    widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
    widget.rect = fitz.Rect(60, 400, 300, 460)
    page.add_widget(widget)
    doc.save(destino)
    doc.close()
    return destino


def pdf_falsos_positivos(destino: Path) -> Path:
    """18 — Texto jurídico sem dados pessoais, para medir falsos positivos."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            "O Supremo Tribunal Federal firmou entendimento no Tema 1007.",
            "A Defensoria Publica da Uniao atua nos termos da Lei Complementar 80.",
            "O Instituto Nacional do Seguro Social indeferiu o requerimento.",
            "Aplica-se o artigo 203 da Constituicao Federal de 1988.",
            "O Tribunal Regional Federal da 1a Regiao negou provimento.",
            "Sao Paulo, Minas Gerais e Rio de Janeiro sao unidades federativas.",
            "Lei n. 8.213/1991 e Decreto n. 3.048/1999 regem a materia.",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


def pdf_multiplas_paginas_lote(destino: Path, nome: str, cpf: str) -> Path:
    """23/24 — Documento de lote com entidade conhecida, para testar consistência."""
    doc = fitz.open()
    page = _nova(doc)
    _escrever(
        page,
        [
            f"Peticao referente a {nome}.",
            f"CPF: {cpf}",
            f"Processo n. {PROCESSO_TESTE}",
        ],
    )
    doc.save(destino)
    doc.close()
    return destino


#: Registro de todas as fixtures simples (nome do arquivo -> função geradora).
FIXTURES = {
    "01_texto_cpf.pdf": pdf_texto_com_cpf,
    "02_digitalizado.pdf": pdf_digitalizado,
    "03_hibrido.pdf": pdf_hibrido,
    "04_nome_repetido.pdf": pdf_nome_repetido,
    "05_nomes_iguais.pdf": pdf_nomes_iguais,
    "06_cpf_formatos.pdf": pdf_cpf_formatos,
    "07_cnpj_cep.pdf": pdf_cnpj_cep,
    "08_processo_cnj.pdf": pdf_processo_cnj,
    "09_dados_bancarios.pdf": pdf_dados_bancarios,
    "10_nome_em_imagem.pdf": pdf_nome_em_imagem,
    "11_cabecalho_rodape.pdf": pdf_cabecalho_rodape,
    "12_anotacao.pdf": pdf_com_anotacao,
    "13_metadados.pdf": pdf_metadados,
    "14_anexo.pdf": pdf_com_anexo,
    "15_ilegivel_ocr.pdf": pdf_ilegivel_ocr,
    "16_malformado.pdf": pdf_malformado,
    "17_assinatura.pdf": pdf_com_assinatura,
    "18_falsos_positivos.pdf": pdf_falsos_positivos,
}


def gerar_todas(pasta: Path) -> dict[str, Path]:
    """Gera todas as fixtures em uma pasta e devolve o mapa nome -> caminho."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    criadas: dict[str, Path] = {}
    for nome, funcao in FIXTURES.items():
        caminho = pasta / nome
        funcao(caminho)
        criadas[nome] = caminho
    return criadas


if __name__ == "__main__":  # pragma: no cover - uso manual
    import sys

    destino = Path(sys.argv[1] if len(sys.argv) > 1 else "fixtures_geradas")
    criadas = gerar_todas(destino)
    for nome, caminho in criadas.items():
        print(f"{nome}: {caminho}")
