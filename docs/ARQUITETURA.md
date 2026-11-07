# Arquitetura

## 1. Visão geral

O aplicativo tem duas camadas bem separadas:

* **`anonimizador_dpu/core/`** — todo o processamento documental. Não importa
  nada de interface gráfica e pode ser usado por script, o que permite testar
  cada etapa isoladamente.
* **`anonimizador_dpu/app/`** — interface Qt (PySide6). Só orquestra: seleciona
  arquivos, apresenta resultados, coleta decisões humanas e dispara as tarefas
  em segundo plano.

A fronteira é deliberada: nenhum módulo de `core/` pode depender de `app/`.

## 2. Componentes

| Módulo | Responsabilidade | Não faz |
|---|---|---|
| `models.py` | Estruturas de dados, enumerações, mascaramento e hash de sessão. | Não executa lógica de negócio. |
| `config.py` | Configuração e política, persistidas em JSON local. | Não acessa rede. |
| `security.py` | Bloqueio de rede, validação de caminhos, limites, temporários, hash, cópia de trabalho. | Não conhece PDF. |
| `audit_logger.py` | Log com filtro que mascara padrões de dados pessoais. | Nunca grava o texto dos autos. |
| `pdf_inspector.py` | Inspeção estrutural e lista de riscos. | Não altera o documento. |
| `text_extractor.py` | Texto linearizado + mapa de posições; anotações, formulários, links e metadados. | Não detecta nada. |
| `ocr_engine.py` | OCR local com Tesseract e conversão de coordenadas px → pontos. | Não baixa idiomas. |
| `brazilian_validators.py` | Dígitos verificadores e formatos brasileiros. | Não consulta bases externas. |
| `entity_detector.py` | Regras, contexto, heurística de nomes, NER local opcional. | Não decide o que será redigido. |
| `lexico_pt.py` | Léxico local: vocabulário que afasta pessoa, prenomes, sobrenomes e sufixos de medicamento. | Embutido no código; nada é baixado. |
| `candidate_manager.py` | Deduplicação, entidades, pseudônimos, decisões. | Não grava nada em disco. |
| `redaction_engine.py` | Redação efetiva (texto e pixels) e conferência imediata. | Não decide veredito. |
| `image_redaction.py` | Conferência visual de áreas e reconstrução de páginas. | Não detecta dados. |
| `metadata_cleaner.py` | Metadados, XMP, anotações, formulários, links, marcadores, `scrub`. | Não remove o que a configuração mandou preservar — reporta como pendência. |
| `attachment_inspector.py` | Inventário de arquivos incorporados e riscos. | Nunca abre nem executa o anexo. |
| `output_validator.py` | Validação independente do arquivo gravado e veredito. | Não reaproveita estado do mecanismo de redação. |
| `report_generator.py` | Relatórios JSON e HTML. | Nunca escreve dados pessoais originais. |
| `pipeline.py` | Orquestra as etapas e o cancelamento. | Não contém regra de detecção. |

## 3. Fluxo de dados

```
PDF original (somente leitura)
        │
        ▼
 [1] pdf_inspector ──► Inspecao (páginas, estruturas, riscos, SHA-256)
        │
        ▼
 [2] text_extractor ──► PaginaTexto.texto_pdf + palavras_pdf (posições exatas)
        │                                   │
        │   páginas digitalizadas/híbridas  │
        ▼                                   │
 [2b] ocr_engine ─────► texto_ocr + palavras_ocr (bbox em pontos da página)
        │                                   │
        ▼                                   ▼
 [3] entity_detector ──► Achados ──► Candidatos (com bbox resolvida)
        │
        ▼
 [4] candidate_manager ──► deduplicação texto/OCR, entidades, pseudônimos
        │
        ▼
 [5] REVISÃO HUMANA (app/ui/review_panel.py)
        │
        ▼
 [6] redaction_engine ──► cópia de trabalho ──► add_redact_annot ──►
                          apply_redactions(text=REMOVE, images=PIXELS)
        │
        ▼
 [7] metadata_cleaner + attachment_inspector ──► scrub e limpeza
        │
        ▼
      PDF de saída gravado em disco (garbage=4, clean=True)
        │
        ▼
 [8] output_validator ──► reabre o arquivo, reextrai, repete OCR, confere áreas,
                          procura identificadores conhecidos ──► Veredito
        │
        ▼
 [9] report_generator ──► relatório JSON + HTML (sem dados pessoais)
```

## 4. Decisões técnicas

### 4.1 Mapa de posições em vez de busca textual

A detecção roda sobre um texto **linearizado a partir das palavras** do PDF
(`page.get_text("words")`), e cada palavra registra o intervalo que ocupa nesse
texto. Mapear uma ocorrência de volta para coordenadas é, então, uma operação
exata.

A alternativa comum — detectar no texto e depois chamar `search_for()` — falha
com quebras de linha, hifenização e repetições, e pode redigir a ocorrência
errada. A abordagem adotada elimina essa classe de falha.

### 4.2 Redação por remoção, não por cobertura

`page.apply_redactions(text=PDF_REDACT_TEXT_REMOVE, images=PDF_REDACT_IMAGE_PIXELS)`
remove o texto do fluxo de conteúdo e substitui os pixels das imagens dentro da
área. O teste `test_conteudo_removido_tambem_do_fluxo_interno` verifica os
*streams* do PDF gravado, e não apenas o resultado da extração de texto.

### 4.3 Texto e OCR são fontes distintas

Numa página híbrida, o mesmo CPF pode aparecer na camada textual e na imagem.
As duas detecções são produzidas separadamente e depois unidas pelo
`candidate_manager`, que:

* evita a contagem dupla no relatório;
* **preserva as duas áreas**, porque a camada de texto e a camada de imagem
  precisam ser redigidas separadamente;
* marca a origem como `TEXTO_E_OCR`.

Ocorrências do mesmo valor vindas da **mesma** fonte não são unidas: são
ocorrências diferentes do documento e podem pertencer a pessoas distintas.

### 4.4 Chave de entidade e pseudônimos

* Para identificadores numéricos, a chave ignora a pontuação: `529.982.247-25`
  e `52998224725` são a mesma entidade e recebem o mesmo pseudônimo.
* Para nomes, a chave é o **nome completo** normalizado (sem acentos, sem
  diferença de caixa). O primeiro nome isolado nunca é usado como chave.
* O prefixo do pseudônimo vem do papel processual inferido do contexto
  (`[ASSISTIDO_1]`, `[TESTEMUNHA_2]`, `[PERITO_1]`), o que preserva a leitura
  jurídica do documento.
* Homônimos podem ser separados pelo usuário na revisão
  (`GerenciadorCandidatos.separar_entidade`).
* O mapa pseudônimo → valor original vive **apenas em memória** e só é
  materializado se o usuário autorizar explicitamente.

### 4.5 Resolução de sobreposições entre detectores

Quando dois detectores marcam regiões que se cruzam:

* intervalos idênticos ou sobreposição parcial — prevalece o de maior confiança;
* **contenção** (o CEP dentro do endereço) — o externo é mantido e o interno
  também, desde que sua confiança não seja menor. Assim o endereço completo é
  redigido sem perder a marcação específica do CEP, e um falso positivo fraco
  contido em uma detecção mais forte (`"Rua das Flores"` como nome de pessoa)
  é descartado.

### 4.6 Validação independente

O validador **reabre o arquivo gravado** e refaz o trabalho com outro caminho de
código: extração direta (`get_text("text")`, sem o mapa de palavras), OCR de
verificação e busca pelos identificadores conhecidos da sessão. Ele não confia
em nenhuma estrutura em memória produzida pela redação.

### 4.7 Bloqueio de rede como garantia verificável

`security.rede_bloqueada()` substitui `socket.socket`, `socket.create_connection`
e `socket.getaddrinfo` enquanto o bloco executa. Toda a inspeção, análise e
processamento rodam dentro desse contexto. O teste
`test_processamento_nao_usa_rede` confirma que nenhum socket é sequer aberto
durante um processamento completo.

### 4.8 Cancelamento cooperativo

O cancelamento é um `threading.Event` consultado entre páginas e entre
documentos. Um processamento cancelado produz relatório com
`cancelado = True` e veredito **REPROVADO**: o arquivo de saída existe, mas
nunca é apresentado como pronto.

### 4.9 Bloqueios de aprovação

A classificação final é calculada em `output_validator.decidir_veredito`. Nenhuma
configuração permite ignorar um bloqueio crítico; a opção
`permitir_aprovacao_com_ressalvas` alcança apenas riscos de severidade *aviso*.

Bloqueiam a aprovação, entre outros: identificador original ainda recuperável,
falha de redação, área não determinada com segurança, anexo não analisado,
portfólio PDF, camadas de conteúdo opcional, assinatura digital, página não
examinada, OCR indisponível para página com imagem e ocorrência pendente de
decisão humana.

## 5. Dependências

| Biblioteca | Papel | Alternativa considerada |
|---|---|---|
| PyMuPDF | Leitura, inspeção, redação com remoção de pixels, `scrub`. | `pikepdf` + `pdfplumber`: não oferecem redação com remoção de pixels de imagem em uma única operação. |
| pytesseract + Tesseract | OCR local com posições por palavra. | OCR em nuvem: proibido pelos requisitos. |
| Pillow | Conversão do *pixmap* para imagem do OCR. | — |
| PySide6 | Interface Windows. | Tkinter: insuficiente para a tela de revisão. |
| numpy / OpenCV | Apoio numérico e de imagem. | — |

**Reconhecimento de entidades por modelo (opcional).** `entity_detector`
carrega um modelo spaCy a partir de um **diretório local** informado em
`deteccao.modelo_ner_local`; se não houver modelo, o aplicativo segue com as
regras determinísticas. Nenhum download é feito. Presidio não foi adotado nesta
versão por acrescentar dependências pesadas e por seus reconhecedores
brasileiros serem menos específicos que os validadores implementados aqui.

## 6. Pontos de extensão

* **Novo detector**: acrescentar a expressão em `entity_detector.py`, o
  validador em `brazilian_validators.py`, a categoria em `models.CATEGORIAS_INFO`
  e o prefixo em `candidate_manager.PREFIXO_PSEUDONIMO`.
* **Nova verificação de saída**: acrescentar ao `output_validator.validar_saida`
  e, se bloqueante, ao `decidir_veredito`.
* **Novo formato de relatório**: `report_generator.montar_json` é a fonte única;
  qualquer formato novo deve consumi-la para herdar a minimização de dados.
