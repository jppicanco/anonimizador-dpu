# Anonimizador DPU

Aplicativo desktop para Windows 10 e 11 que prepara cópias anonimizadas de
processos judiciais em PDF, **processando tudo localmente**, sem enviar
documentos, textos, imagens ou metadados a qualquer serviço externo.

> **Aviso que não é opcional**
> A aprovação técnica automatizada **não garante anonimização integral** e
> **não substitui** a revisão humana nem a avaliação de conformidade com a
> regulamentação da DPU. Antes de qualquer uso com processos sigilosos, a
> ferramenta precisa ser validada pela área de tecnologia e autorizada pela
> instância competente.

---

## 1. Objetivo

Permitir que o membro da DPU produza, no próprio computador, uma versão de um
processo judicial em que os dados pessoais tenham sido **efetivamente removidos**
do arquivo — e não apenas cobertos por retângulos pretos —, com revisão humana
das ocorrências, validação independente do resultado e relatório auditável.

## 2. Funcionalidades

| Etapa | O que faz |
|---|---|
| Inspeção estrutural | Classifica cada página (texto, digitalizada, híbrida, vazia) e inventaria formulários, anotações, links, arquivos incorporados, camadas, assinaturas digitais e metadados, produzindo a lista de riscos. |
| Extração | Extrai o texto selecionável com o mapa de posições de cada palavra. |
| OCR local | Executa Tesseract em português nas páginas digitalizadas, registrando cobertura, confiança e falhas. |
| Detecção | Combina expressões regulares, validação de dígitos verificadores, análise de contexto e heurística de nomes para localizar dados pessoais. |
| Revisão humana | Tudo que foi detectado já entra **marcado para remoção**; o revisor desmarca o que deve permanecer no texto. A tela traz situação, confiança destacada por faixa, origem, pseudônimo, trecho minimizado, decisão individual ou em lote, alteração de categoria, separação de homônimos e marcação manual de regiões. |
| Redação efetiva | Remove o texto do fluxo de conteúdo do PDF e os pixels correspondentes nas imagens; opcionalmente escreve o pseudônimo no lugar. |
| Metadados e estruturas | Limpa metadados, XMP, anotações, campos de formulário, links, marcadores, anexos, JavaScript e texto oculto. |
| Validação independente | Reabre o arquivo gravado, reextrai o texto, repete o OCR, confere as áreas, examina metadados e anexos e procura os identificadores originais da sessão. |
| Relatórios | JSON e HTML, com hash SHA-256 da saída e **sem** dados pessoais originais. |

### O que o aplicativo nunca faz

* Não acessa a internet. Durante todo o processamento, o acesso a sockets é
  **bloqueado no processo** (`core/security.py`), de modo que qualquer tentativa
  de conexão, inclusive de bibliotecas de terceiros, falha de forma visível.
* Não altera o arquivo original.
* Não baixa modelos, binários ou pacotes durante o uso.
* Não envia o documento anonimizado a nenhum outro programa ou serviço.
* Não grava o texto dos autos, nomes, CPFs ou endereços em log.
* Não gera tabela de reversão (pseudônimo → valor original) por padrão.
* Não oferece botão que ignore um bloqueio crítico de aprovação.

## 3. Requisitos

* Windows 10 ou Windows 11 (também funciona em Linux para desenvolvimento).
* Python 3.11 ou superior (validado em 3.13.13).
* **Tesseract OCR 5.x** instalado, com o idioma português (`por.traineddata`).
* Nenhum privilégio de administrador é exigido para usar o aplicativo.

### 3.1 Instalação do Tesseract (operação separada, feita uma única vez)

1. Baixe o instalador oficial para Windows (projeto UB Mannheim) em uma máquina
   com acesso à internet e, se necessário, transporte o instalador.
2. Instale em `C:\Program Files\Tesseract-OCR`.
3. Durante a instalação, marque o idioma **Portuguese**. O arquivo
   `por.traineddata` deve ficar em `C:\Program Files\Tesseract-OCR\tessdata\`.
4. Confirme no prompt: `tesseract --list-langs` deve listar `por`.

Se o Tesseract estiver em outro caminho, informe-o no arquivo de configuração
(`%APPDATA%\anonimizador_dpu\config.json`, campo `ocr.caminho_tesseract`).

## 4. Instalação

```bat
cd E:\Anonimizador
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Para desenvolvimento e testes:

```bat
pip install -r requirements-dev.txt
```

Verifique o ambiente antes do primeiro uso:

```bat
python scripts\verificar_ambiente.py
```

## 5. Como executar

Interface gráfica:

```bat
python -m anonimizador_dpu.app.main
```

Gerar os documentos sintéticos de teste (nenhum dado real):

```bat
python scripts\gerar_fixtures.py C:\temp\fixtures_anonimizador
```

## 6. Como executar os testes

```bat
python -m pytest
```

Saída esperada no ambiente de referência: **324 testes aprovados**. Os testes
que dependem de OCR são automaticamente ignorados se o Tesseract não estiver
instalado — nesse caso, a cobertura do exame é menor e isso é registrado.

Para ver quais foram ignorados:

```bat
python -m pytest -rs
```

## 7. Como gerar o executável Windows

```bat
pip install pyinstaller
python -m PyInstaller scripts\anonimizador_dpu.spec --noconfirm
```

ou, simplesmente, `scripts\gerar_executavel.bat`.

O resultado fica em `dist\AnonimizadorDPU\AnonimizadorDPU.exe` e ocupa
aproximadamente **190 MB**.

> **Feche o aplicativo antes de reconstruir.** Com ele aberto, o Windows mantém
> os arquivos travados e o PyInstaller aborta com *acesso negado* — deixando no
> lugar o executável anterior, que parece novo e não é.

O executável **não** inclui o reconhecimento de entidades por modelo local
(spaCy), que é opcional. Embarcá-lo arrastaria `torch` e correlatos, levando o
pacote a mais de 1,4 GB. Quem precisar desse recurso deve executar a aplicação
a partir do código-fonte.

### 7.1 Pacote para distribuição

```bat
python scripts\montar_pacote.py
```

Produz `dist\AnonimizadorDPU.zip`, autocontido, com:

| Conteúdo | Observação |
|---|---|
| `aplicativo\` | O executável e suas bibliotecas. |
| `aplicativo\tesseract\` | **Tesseract embutido** (Apache-2.0), com `por`, `eng` e `osd`. O aplicativo o procura ao lado de si antes de qualquer outro caminho. |
| `documentacao\` | Manual, limitações, segurança, arquitetura e testes. |
| `codigo-fonte\` | Exigido pela AGPL-3.0 do PyMuPDF — e porque uma ferramenta de anonimização que ninguém pode auditar não deveria ser usada. |
| `INSTALAR.txt` | Instruções em linguagem simples, para quem não é da área. |
| `LICENCAS.txt` | Componentes de terceiros e suas licenças. |

Dentro do ZIP há uma única pasta, `AnonimizadorDPU/`. Quem recebe descompacta
e clica no executável. **Não exige instalação, não exige administrador e não
baixa nada.**

O `INSTALAR.txt` começa mandando **desbloquear o ZIP** (botão direito →
Propriedades → "Desbloquear") antes de descompactar: arquivo baixado chega com
a marca de origem do Windows, e ela se propaga para tudo que sai de dentro.
Também explica o aviso do SmartScreen na primeira execução — esperado, porque
o executável não tem assinatura digital comercial.

O texto para enviar junto está em `handoffs/MENSAGEM_AOS_COLEGAS.md`.

Teste o pacote em uma máquina limpa e **sem conexão com a internet** antes de
distribuí-lo.

### Atalhos para Windows

| Script | Função |
|---|---|
| `scripts\instalar.bat` | Cria o `.venv`, instala as dependências e verifica o ambiente. |
| `scripts\executar.bat` | Abre o aplicativo. |
| `scripts\testar.bat` | Executa a suíte de testes. |
| `scripts\gerar_executavel.bat` | Gera o executável com o PyInstaller. |
| `scripts\gerar_pacote.bat` | Gera o executável **e** monta o ZIP de distribuição. |

## 8. Configuração

A configuração é gravada em `%APPDATA%\anonimizador_dpu\config.json` e cobre:
categorias ativas, limiares de confiança, modo de redação (pseudônimo ou
tarja), idiomas e resolução do OCR, limites de tamanho/páginas/tempo e política
de aprovação. Nenhuma opção habilita acesso à rede.

## 9. Estrutura do projeto

```
anonimizador_dpu/
  app/
    main.py                  ponto de entrada da interface
    ui/
      main_window.py         janela principal (5 etapas)
      review_panel.py        tela de revisão humana
      page_viewer.py         visualização e marcação manual de regiões
      workers.py             execução em segundo plano e cancelamento
  core/
    models.py                estruturas de dados e enumerações
    config.py                configuração e política
    security.py              bloqueio de rede, caminhos, limites, temporários
    audit_logger.py          log com supressão de dados pessoais
    pdf_inspector.py         inspeção estrutural
    text_extractor.py        extração de texto com mapa de posições
    ocr_engine.py            OCR local (Tesseract)
    brazilian_validators.py  CPF, CNPJ, CEP, telefone, CNJ, PIS, título, CNH…
    entity_detector.py       detecção por regras, contexto e heurística
    lexico_pt.py             léxico local: nomes, vocabulário jurídico, medicamentos
    candidate_manager.py     deduplicação, entidades e pseudônimos
    redaction_engine.py      redação efetiva (texto e imagem)
    image_redaction.py       conferência de áreas e reconstrução de páginas
    metadata_cleaner.py      metadados e estruturas internas
    attachment_inspector.py  arquivos incorporados
    output_validator.py      validação independente e veredito
    report_generator.py      relatórios JSON e HTML
    pipeline.py              orquestração das etapas
tests/                       suíte automatizada e geradores de PDFs sintéticos
scripts/                     verificação de ambiente, fixtures e empacotamento
docs/                        arquitetura, segurança, limitações, manual, testes
```

## 10. Documentação

* [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md) — componentes, fluxo de dados e decisões técnicas.
* [`docs/SEGURANCA.md`](docs/SEGURANCA.md) — garantias reais, limites e tratamento de falhas.
* [`docs/LIMITACOES.md`](docs/LIMITACOES.md) — o que a ferramenta **não** resolve.
* [`docs/MANUAL_USUARIO.md`](docs/MANUAL_USUARIO.md) — passo a passo de utilização.
* [`docs/TESTES.md`](docs/TESTES.md) — testes executados, resultados reais e lacunas.

## 11. Componentes de terceiros e licenças

| Componente | Licença | Observação sobre redistribuição |
|---|---|---|
| PyMuPDF 1.26.3 | AGPL-3.0 (ou licença comercial da Artifex) | **Atenção:** distribuir o executável implica obrigações da AGPL, inclusive disponibilizar o código-fonte. Requer análise jurídica antes de qualquer distribuição institucional. |
| PySide6 6.12.0 | LGPL-3.0 | Permite uso em aplicação institucional; manter as bibliotecas substituíveis. |
| Pillow | MIT-CMU | Redistribuição livre com aviso de licença. |
| pytesseract | Apache-2.0 | Apenas a interface Python; o binário é separado. |
| Tesseract OCR 5.x | Apache-2.0 | Instalado separadamente; não é redistribuído pelo projeto. |
| numpy, OpenCV | BSD-3 / Apache-2.0 | Redistribuição livre com aviso de licença. |

Em razão da licença do PyMuPDF, o projeto é publicado sob **AGPL-3.0 ou
posterior**. A decisão sobre a forma de distribuição interna na DPU deve
considerar esse ponto.

## 12. Antes de usar com processos reais

1. Execute `python scripts\verificar_ambiente.py`.
2. Gere as fixtures sintéticas e processe-as integralmente, conferindo os
   relatórios.
3. Leia `docs/LIMITACOES.md` por inteiro.
4. Submeta a ferramenta à avaliação da área de tecnologia da DPU e à instância
   competente em proteção de dados, conforme `docs/SEGURANCA.md`, seção
   "Pendências para validação institucional".
