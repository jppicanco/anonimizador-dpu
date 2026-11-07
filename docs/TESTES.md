# Testes

## 1. Ambiente de execução

| Item | Valor |
|---|---|
| Data da execução | 26/10/2026, 15:07 |
| Sistema | Windows 11 Pro 10.0.26300 (AMD64) |
| Python | 3.13.13 |
| pytest | 9.1.1 |
| PyMuPDF | 1.26.3 |
| Tesseract | 5.5.0.20241111 (`C:\Program Files\Tesseract-OCR`), idiomas `eng`, `osd`, `por` |
| PySide6 | 6.12.0 |

Comando:

```bat
python -m pytest
```

## 2. Resultado real

```
324 passed in 11.38s
```

**324 testes aprovados, 0 reprovados, 0 ignorados** (29/10/2026). Nenhum teste foi pulado:
o Tesseract com português estava instalado, de modo que todos os testes
marcados com `@requer_ocr` foram efetivamente executados.

### Distribuição

| Arquivo | Testes |
|---|---:|
| `tests/test_brazilian_validators.py` | 37 |
| `tests/test_entity_detector.py` | 25 |
| `tests/test_end_to_end.py` | 17 |
| `tests/test_candidate_manager.py` | 16 |
| `tests/test_security.py` | 14 |
| `tests/test_output_validator.py` | 16 |
| `tests/test_pdf_inspector.py` | 10 |
| `tests/test_redaction_engine.py` | 9 |
| `tests/test_ocr_engine.py` | 6 |
| `tests/test_text_extractor.py` | 6 |
| `tests/test_metadata_cleaner.py` | 5 |
| `tests/test_report_generator.py` | 5 |
| `tests/test_attachments.py` | 4 |
| `tests/test_tema_interface.py` | 9 |
| `tests/test_falsos_positivos_nome.py` | 130 |
| `tests/test_coerencia_de_redacao.py` | 8 |
| `tests/test_validacao_palavra_e_metadado.py` | 6 |
| **Total** | **324** |

### Testes mais lentos (OCR real)

```
0.87s  test_end_to_end.py::test_pagina_ilegivel_impede_aprovacao
0.75s  test_end_to_end.py::test_fluxo_completo_documento_digitalizado
0.69s  test_end_to_end.py::test_pagina_hibrida_trata_texto_e_imagem
0.65s  test_end_to_end.py::test_nome_apenas_em_imagem_e_encontrado
```

## 3. Documentos sintéticos usados

Gerados por `tests/fixtures/gerador.py` com dados **deliberadamente fictícios**
("Pessoa Teste Alfa", CPF de teste 529.982.247-25). Nenhum processo judicial
real foi utilizado em nenhum momento do desenvolvimento ou dos testes.

| Arquivo | Conteúdo |
|---|---|
| `01_texto_cpf.pdf` | Petição com texto selecionável: processo CNJ, nome, data de nascimento, CPF, RG, endereço, CEP, telefone, e-mail, CNPJ, NB. |
| `02_digitalizado.pdf` | Página exclusivamente em imagem com nome, CPF, endereço, CEP e telefone. |
| `03_hibrido.pdf` | Texto selecionável + imagem com outros dados. |
| `04_nome_repetido.pdf` | 12 páginas com o mesmo nome repetido (36 ocorrências). |
| `05_nomes_iguais.pdf` | Duas pessoas distintas com o mesmo nome, diferenciadas pelo CPF. |
| `06_cpf_formatos.pdf` | CPF com e sem pontuação, CPF com dígito inválido, números que não são CPF. |
| `07_cnpj_cep.pdf` | CNPJ e CEP com e sem pontuação. |
| `08_processo_cnj.pdf` | Número CNJ válido e com dígito verificador incorreto. |
| `09_dados_bancarios.pdf` | Banco, agência, conta, chave Pix (UUID) e cartão em tabela. |
| `10_nome_em_imagem.pdf` | Nome presente **apenas** dentro de imagem incorporada. |
| `11_cabecalho_rodape.pdf` | Dados pessoais em cabeçalho e rodapé de três páginas. |
| `12_anotacao.pdf` | CPF e telefone dentro de anotação (comentário). |
| `13_metadados.pdf` | Nome, CPF, processo e CEP nos metadados. |
| `14_anexo.pdf` | Arquivo incorporado `.xlsx` (formato não suportado). |
| `15_ilegivel_ocr.pdf` | Imagem de ruído, ilegível para OCR. |
| `16_malformado.pdf` | Cabeçalho `%PDF` com estrutura corrompida. |
| `17_assinatura.pdf` | Campo de assinatura digital. |
| `18_falsos_positivos.pdf` | Texto jurídico com órgãos, leis e unidades federativas, **sem** dados pessoais. |

## 4. Cobertura dos 26 testes obrigatórios

| # | Teste exigido | Onde | Resultado |
|---|---|---|---|
| 1 | PDF com texto selecionável e CPF | `test_end_to_end::test_fluxo_completo_documento_de_texto`, `test_redaction_engine::test_texto_original_e_removido_do_pdf` | Aprovado |
| 2 | PDF digitalizado com CPF e endereço | `test_end_to_end::test_fluxo_completo_documento_digitalizado` | Aprovado (OCR real) |
| 3 | PDF híbrido com texto e imagens | `test_end_to_end::test_pagina_hibrida_trata_texto_e_imagem` | Aprovado |
| 4 | Nome repetido em dezenas de páginas | `test_redaction_engine::test_nome_repetido_em_varias_paginas` | Aprovado |
| 5 | Pessoas diferentes com nomes iguais | `test_candidate_manager::test_homonimos_podem_ser_separados`, `test_end_to_end::test_nomes_iguais_pessoas_distintas` | Aprovado |
| 6 | CPF com e sem pontuação | `test_entity_detector::TestCPF`, `test_brazilian_validators::TestCPF` | Aprovado |
| 7 | CNPJ e CEP | `test_entity_detector::TestCNPJeCEP`, `test_brazilian_validators` | Aprovado |
| 8 | Número de processo no padrão CNJ | `test_entity_detector::TestProcesso`, `test_brazilian_validators::TestProcessoCNJ` | Aprovado |
| 9 | Dados bancários em tabela | `test_entity_detector::TestDadosBancarios`, `test_end_to_end::test_dados_bancarios_em_tabela` | Aprovado |
| 10 | Nome em imagem incorporada | `test_end_to_end::test_nome_apenas_em_imagem_e_encontrado` | Aprovado (OCR real) |
| 11 | Dados em cabeçalho e rodapé | `test_redaction_engine::test_cabecalho_e_rodape_sao_redigidos` | Aprovado |
| 12 | Dados pessoais em anotação | `test_metadata_cleaner::test_anotacoes_sao_lidas_e_removidas`, `test_end_to_end::test_anotacao_com_dados_e_tratada` | Aprovado |
| 13 | Metadados contendo nome fictício | `test_metadata_cleaner::test_metadados_com_nome_sao_removidos`, `test_end_to_end::test_metadados_sao_limpos_no_fluxo` | Aprovado |
| 14 | Arquivo incorporado não suportado | `test_attachments.py` (4 testes), `test_output_validator::test_anexo_nao_tratado_impede_aprovacao` | Aprovado |
| 15 | Página ilegível para OCR | `test_ocr_engine::test_pagina_ilegivel_nao_e_considerada_examinada`, `test_end_to_end::test_pagina_ilegivel_impede_aprovacao` | Aprovado |
| 16 | PDF malformado | `test_pdf_inspector::test_pdf_malformado_nao_derruba_a_aplicacao`, `test_end_to_end::test_pdf_malformado_nao_interrompe_o_lote` | Aprovado |
| 17 | Documento com assinatura digital | `test_pdf_inspector::test_assinatura_digital_e_detectada`, `test_output_validator::test_assinatura_digital_impede_aprovacao` | Aprovado |
| 18 | Falsos positivos em texto jurídico | `test_entity_detector::TestFalsosPositivos`, `test_end_to_end::test_falsos_positivos_em_texto_juridico` | Aprovado — zero ocorrências no texto jurídico sintético |
| 19 | Reabertura e reextração do PDF de saída | `test_output_validator::test_reabertura_e_reextracao` | Aprovado |
| 20 | Pesquisa de dados identificadores residuais | `test_output_validator::test_identificador_residual_reprova_o_documento` | Aprovado — redação sabotada é detectada e REPROVADA |
| 21 | Falha no mecanismo de redação | `test_redaction_engine::test_ocorrencia_sem_area_vira_falha_critica` | Aprovado |
| 22 | Cancelamento durante o processamento | `test_end_to_end::test_cancelamento_encerra_de_forma_controlada`, `test_cancelamento_durante_a_analise` | Aprovado |
| 23 | Processamento em lote | `test_end_to_end::test_processamento_em_lote_preserva_ordem` | Aprovado |
| 24 | Consistência dos pseudônimos entre documentos | `test_end_to_end::test_consistencia_de_pseudonimos_entre_documentos`, `test_candidate_manager::TestPseudonimos` | Aprovado |
| 25 | Tentativa de sobrescrever o original | `test_security::TestProtecaoDoOriginal` (4 testes) | Aprovado |
| 26 | Independência de conexão externa | `test_security::TestBloqueioDeRede` (4 testes), `test_end_to_end::test_processamento_nao_usa_rede` | Aprovado — nenhum socket é aberto durante o processamento |

## 5. Testes adicionais relevantes

* **Conteúdo removido do fluxo interno do PDF** — `test_redaction_engine::test_conteudo_removido_tambem_do_fluxo_interno`
  inspeciona os *streams* do arquivo gravado, não apenas a extração de texto.
* **Relatório sem dados pessoais** — `test_report_generator::test_relatorio_nao_contem_dados_pessoais`
  verifica JSON e HTML contra CPF, nome, processo e CEP, inclusive na forma sem
  pontuação.
* **Serialização de candidato não expõe o valor** — `test_candidate_manager::test_serializacao_nao_expoe_o_valor_original`.
* **Tabela de reversão exige autorização** — `test_candidate_manager::test_tabela_de_reversao_exige_autorizacao`.
* **Mapeamento texto → coordenadas** — `test_text_extractor` confirma que cada
  palavra aponta exatamente para o seu trecho no texto linearizado.
* **Decisão de veredito** — `test_output_validator::TestDecisaoDeVeredito`
  (7 testes), incluindo a impossibilidade de um bloqueio crítico virar ressalva.
* **Sessão em thread separada** — `test_end_to_end::test_sessao_em_thread_separada`,
  que reproduz o uso pela interface gráfica.

## 6. Verificações manuais realizadas

| Verificação | Resultado |
|---|---|
| Abertura da interface gráfica (PySide6 em modo *offscreen*) | A janela é criada, as cinco abas são montadas e o estado do OCR é exibido corretamente. |
| `python scripts\verificar_ambiente.py` | Todas as dependências e o Tesseract com `por` reportados como disponíveis. |
| Processamento manual de `01_texto_cpf.pdf` e `02_digitalizado.pdf` | Vereditos APROVADO NOS TESTES AUTOMATIZADOS; texto de saída conferido manualmente, com pseudônimos no lugar dos dados e nenhum dado original presente. |
| Geração dos relatórios JSON e HTML | Arquivos produzidos ao lado da saída, com veredito, hashes e riscos. |
| Empacotamento com PyInstaller 6.21.0 | Executado. `dist\AnonimizadorDPU\AnonimizadorDPU.exe`, 189,4 MB no total. |
| Execução do executável gerado | O aplicativo inicia, carrega a interface e grava o log, sem erro em `stderr`. |

### 6.1 Problemas encontrados e corrigidos no empacotamento

O primeiro empacotamento produziu uma pasta de **1,4 GB** e, nas tentativas de
redução, dois defeitos reais apareceram — ambos corrigidos:

1. **Dependências indevidas (1,4 GB → 189 MB).** O `import spacy`, que está
   protegido por `try/except` e é opcional, foi enxergado pela análise estática
   do PyInstaller, que passou a embarcar `torch` (312 MB), `bitsandbytes`,
   `transformers`, `cv2`, `scipy`, `pyarrow` e `llvmlite`. Esses pacotes foram
   adicionados a `excludes` no `.spec`. **Consequência documentada:** o
   executável não oferece o reconhecimento de entidades por modelo local; quem
   precisar dele deve executar a aplicação a partir do código-fonte.
2. **Ponto de entrada inadequado.** Usar `anonimizador_dpu/app/main.py`
   diretamente como script inicial causava
   `ImportError: attempted relative import with no known parent package`,
   porque o PyInstaller o executa como `__main__`, sem pacote pai. Foi criado
   `scripts/executavel.py`, que importa o pacote pelo nome absoluto.

Houve ainda uma tentativa de filtrar as bibliotecas Qt por lista positiva, que
removeu `pyside6.abi3.dll` e quebrou o executável com
`ImportError: DLL load failed while importing QtWidgets`. O filtro foi
substituído por uma **lista negativa** explícita dos módulos Qt não utilizados.

> Esses três defeitos só apareceram porque o executável foi efetivamente gerado
> e executado. Um `.spec` escrito e não testado teria sido entregue quebrado.

### 6.2 Defeito de legibilidade sob o tema escuro do Windows

Em uso real, a tabela de revisão apareceu **ilegível**: texto branco sobre as
cores pastel de situação. A causa é que as cores de fundo foram definidas para
tema claro, mas a cor do texto não era definida junto — ela era herdada da
paleta do sistema, que no tema escuro do Windows 11 é branca. O mesmo valia
para a tarja de aviso em HTML e para os destaques de risco e veredito, cujos
tons escuros ficavam com pouco contraste sobre o fundo escuro.

A correção concentrou as cores em `anonimizador_dpu/app/ui/tema.py`, que
detecta a paleta ativa, mantém um conjunto de cores para cada tema e resolve a
cor do texto pela luminância do fundo (critério da WCAG 2.1). O painel de
revisão passou a definir **fundo e texto em conjunto**.

`tests/test_tema_interface.py` fixa a regra: toda situação prevista precisa ter
contraste de pelo menos **4,5:1** nos dois temas, e duas situações não podem
compartilhar a mesma cor. A conferência visual foi feita renderizando o painel
nos dois temas com dados fictícios.

> Este defeito **não aparece em teste automatizado de lógica** e não foi
> detectado na verificação *offscreen*, que confirma que a janela é construída,
> não que ela é legível. É exatamente a classe de problema que só o uso revela —
> e um argumento concreto a favor do piloto com documentos sintéticos antes de
> qualquer distribuição ampla.

### 6.3 Excesso de detecção relatado em uso real

Ao abrir uma decisão de turma recursal, a revisão apareceu tomada por falsos
positivos de **nome de pessoa**: "PODER JUDICIÁRIO", "PEDIDO DE UNIFORMIZAÇÃO",
"CONJUNTO PROBATÓRIO", "ELEMENTOS TÉCNICOS E PERICIAIS", "REEXAME DE PROVA",
"VIA ELEITA", "DISPOSITIVO E TESE", "NAT JUS", nomes de medicamento — dezenas
de ocorrências que não identificam ninguém.

Isso não é só incômodo. **Uma lista cheia de lixo faz o revisor parar de ler**,
e o erro migra para onde importa. Ferramenta ruidosa é ferramenta insegura.

Causas, as duas reais:

1. **Heurística de nome invertida.** Qualquer sequência de palavras iniciadas
   por maiúscula virava candidato a nome, e só era descartada se batesse numa
   lista curta de exclusões. Peça judicial é feita de títulos em caixa alta —
   o detector estava, na prática, marcando os cabeçalhos do documento.
2. **"Conjunto" é palavra de logradouro.** "CONJUNTO PROBATÓRIO" não vinha da
   heurística de nomes: vinha da expressão regular de **endereço**, que aceita
   "Conjunto", "Setor", "Quadra", "Lote" e "Bloco" como início de logradouro.

Correções:

* Criado `anonimizador_dpu/core/lexico_pt.py`: 989 termos que afastam a
  hipótese de pessoa (vocabulário processual, institucional, de prova, de
  saúde, de medicamento e rótulos de papel), 150 palavras funcionais, 711
  prenomes e 392 sobrenomes usuais no Brasil, além de sufixos de denominação
  de medicamento (`-mabe`, `-prazol`, `-sartana`, `-xabana`…).
* A regra passou a ser de **evidência positiva**: rótulo processual, prenome
  ou sobrenome conhecido. Texto em caixa alta **exige** evidência; sem ela, é
  título de seção, não nome.
* As bordas do trecho são aparadas em vez de o candidato ser rejeitado por
  inteiro, porque a expressão atravessa a quebra de linha e arrastava o rótulo
  da linha seguinte (`"MARIA … DOS SANTOS\nREQUERIDO"`).
* Palavra de logradouro ambígua só vale como endereço **com número** no trecho.
  A restrição não alcança "Rua", "Avenida" e afins, porque nome de rua usa
  palavra comum o tempo todo — "Avenida Brasil".
* Contexto de medicamento ("uso contínuo de X", "prescrição de X") afasta a
  hipótese de pessoa, salvo quando há rótulo processual: "o requerente Carlos
  Alberto faz uso de Rivaroxabana" continua detectando a pessoa.

`tests/test_falsos_positivos_nome.py` fixa **106 casos**, construídos a partir
das expressões efetivamente relatadas, e verifica tanto a supressão do ruído
quanto a permanência dos nomes fictícios. Em um texto sintético no estilo de
uma decisão da TNU, a detecção saiu de dezenas de ocorrências para **9, todas
legítimas**: nome, CPF, data de nascimento, endereço, CEP, telefone, e-mail e
número de processo.

> Este defeito não aparecia em nenhum teste porque os documentos sintéticos de
> fixture são curtos e não imitam a densidade de títulos de um acórdão real.
> Foi preciso usar a ferramenta com um documento de verdade para vê-lo.

### 6.4 Oito documentos reais reprovados — e por quê

Em uso real, **os oito documentos de um processo público foram REPROVADOS**
pela validação independente, com o risco `IDENTIFICADOR_RESIDUAL_IMAGEM`:
identificadores confirmados para redação continuavam legíveis na saída.

A validação estava certa, e o diagnóstico revelou quatro defeitos distintos —
nenhum deles na redação em si. Todos eram de **detecção incoerente**: o mesmo
dado era redigido num ponto e deixado em outro, de modo que o documento
continuava identificando a pessoa.

1. **Política de profissionais aplicada por ocorrência, e não por pessoa.**
   "RELATOR: JUIZ FEDERAL Fulano" era excluído pela política; o mesmo nome em
   "assinado eletronicamente por Fulano", sem rótulo, era redigido. Resultado:
   o nome permanecia legível e a redação não protegia ninguém. A política
   passou a valer **por pessoa**, em todo o documento. Além disso, a ocorrência
   mantida deixou de sumir em silêncio: ela aparece na revisão, desmarcada e
   com o motivo à vista.
2. **Número de processo partido na quebra de linha.** O OCR devolve
   `5000446-` numa linha e `50.2021.4.04.7204` na seguinte; a expressão não
   casava. A ocorrência escapava, enquanto a mesma numeração era redigida em
   outro ponto da página. A expressão passou a tolerar espaço e quebra de
   linha — o que é seguro, porque o dígito verificador é conferido em seguida.
3. **Cargo público tratado como nome.** "AGENTE DE POLÍCIA FEDERAL" virava
   nome de pessoa, era redigido num ponto e permanecia em outro.
4. **Nome de doença tratado como nome.** "Doença Pulmonar Obstrutiva Crônica"
   virava nome de pessoa — grave em matéria de saúde, que é o grosso do acervo.

Corrigidos os quatro, os mesmos oito documentos passaram a ser **aprovados nos
testes automatizados**, com zero identificadores residuais.

`tests/test_coerencia_de_redacao.py` fixa os quatro casos, com dados
fictícios.

> Nenhum desses defeitos apareceria nas fixtures sintéticas: elas são curtas,
> não repetem o mesmo nome em contextos diferentes e não têm quebra de linha no
> meio de um número de processo. **Foi preciso processar documentos reais para
> encontrá-los** — e foi a validação independente, não a suíte de testes, que
> os denunciou. É o melhor argumento a favor de ela existir.

### 6.5 Pacote de distribuição — verificado

| Verificação | Resultado |
|---|---|
| `python scripts\montar_pacote.py` | Pasta de **278 MB**, ZIP de **118 MB**, 376 arquivos, íntegro (`zipfile.testzip()`). |
| Conteúdo obrigatório | Executável, Tesseract com `por`/`eng`/`osd`, documentação, licenças e código-fonte — todos presentes. |
| Tesseract embutido, isolado | `tesseract.exe --version` e `--list-langs` respondem a partir da pasta do pacote, lendo o próprio `tessdata`. |
| Aplicativo encontra o Tesseract embutido | Executável aberto com `APPDATA` temporário (simulando máquina sem configuração salva): a linha de estado aponta para `aplicativo\tesseract\tesseract.exe`, e não para a instalação do sistema. |
| OCR real com o binário embutido | Documento digitalizado de 2 páginas processado de ponta a ponta: 2 páginas examinadas por OCR, 11 áreas redigidas, **APROVADO**, zero identificadores residuais. |
| Pasta raiz dentro do ZIP | `AnonimizadorDPU/`. Quem descompacta não recebe uma pasta chamada `AnonimizadorDPU_pacote`. |
| Executável do pacote idêntico ao verificado | MD5 do `.exe` dentro do pacote igual ao de `dist\AnonimizadorDPU\` — o pacote não foi montado sobre uma construção diferente da que passou nos testes acima. |

Pacote gerado em **26/10/2026**:

| | |
|---|---|
| Arquivo | `dist\AnonimizadorDPU.zip` |
| Tamanho | 118 MB, 376 arquivos |
| SHA-256 | `84ac356db8cb3d805f6f733744cc1506048a6d3a6217f0118b56c5c5b727e378` |

O `INSTALAR.txt` instrui a **desbloquear o ZIP** (botão direito → Propriedades
→ "Desbloquear") antes de descompactar. Arquivo baixado da internet ou do
SharePoint chega com a marca de origem do Windows, e a marca se propaga para
todo o conteúdo extraído. O mesmo arquivo explica o aviso do SmartScreen na
primeira execução, esperado num executável sem assinatura digital comercial.

#### Um defeito de empacotamento, de novo mascarado

Duas reconstruções do executável relataram sucesso e **não reconstruíram nada**.
O PyInstaller abortava com `PermissionError: acesso negado` ao limpar
`dist\AnonimizadorDPU\_internal\` — o aplicativo estava **aberto**, e o Windows
mantinha os arquivos travados. O executável antigo permanecia no lugar,
parecendo novo.

O erro passou despercebido porque o comando terminava em `| tail`, e o *pipe*
devolve o código de saída do `tail`, não do PyInstaller. É a mesma classe de
engano já registrado na seção 6.1: **confiar em um "OK" que não foi conferido**.
Só apareceu porque a verificação seguinte comparou a data do executável com a
data da alteração no código.

Correções: `scripts/gerar_pacote.bat` encerra o aplicativo antes de construir e
checa `errorlevel` em cada etapa; o README registra o aviso.

> Conferir o código de saída não é formalidade. Duas vezes neste projeto um
> processo falhou relatando sucesso, e nas duas o que denunciou foi uma
> verificação independente do resultado — não a mensagem do próprio processo.

## 7. Testes **não** executados — lacunas assumidas

1. **Interface gráfica interativa.** A janela foi construída e verificada em
   modo *offscreen*, mas **não há testes automatizados de interação** (cliques,
   arrasto de região, diálogos). O fluxo de revisão humana não foi exercitado
   por teste; foi exercitado apenas pelas chamadas de `core` que ele aciona.
   O contraste das cores é testado (seção 6.2), mas a **aparência** das demais
   telas sob o tema escuro não foi conferida tela a tela.
2. **Executável e pacote — falta a outra máquina.** O pacote foi gerado, o
   aplicativo abre a partir do executável e encontra o Tesseract embutido com
   configuração limpa; o OCR embutido processou um documento digitalizado de
   ponta a ponta (seção 6.5). Em 30/10/2026, o usuário conduziu **pela
   interface do executável do pacote** um lote de seis documentos
   digitalizados (10 páginas no total, todas por OCR): seis aprovados nos
   testes automatizados, zero identificadores residuais, nenhum erro no log.
   Essa lacuna está fechada. **Permanece não testada** a execução em **outra
   máquina**, sem Python e sem internet — obrigatória antes de qualquer
   distribuição.
3. **Windows 10.** Todos os testes rodaram em Windows 11. O funcionamento em
   Windows 10 é esperado, mas não foi verificado.
4. **Documentos reais — amostra de um só processo.** O desenvolvimento usou
   fixtures sintéticas. Posteriormente, com autorização expressa do usuário e
   por se tratar de **processo público, não sigiloso**, oito documentos reais
   foram processados (seção 6.4) — e foi o que revelou quatro defeitos que
   nenhuma fixture teria revelado. Ainda assim, **é um processo só**: o
   comportamento diante de digitalizações ruins, carimbos, manuscritos e
   layouts de outros tribunais **não foi medido**. Nenhum processo sigiloso
   foi usado, e nenhum deve ser até a homologação institucional.
5. **Volume.** O maior documento testado tem 12 páginas. Não houve teste com
   centenas ou milhares de páginas, nem medição de consumo de memória em
   processos extensos.
6. **Portfólio PDF e camadas OCG.** A detecção desses casos é testada
   indiretamente (o código bloqueia a aprovação), mas **não há fixture** de
   portfólio real nem de PDF com camadas, porque gerá-los com PyMuPDF não é
   direto. O caminho de reconstrução por rasterização, portanto, **não foi
   exercitado por teste automatizado**.
7. **Modelo local de reconhecimento de entidades.** O caminho de código que
   carrega spaCy existe e é tolerante a falhas, mas não foi testado com um
   modelo instalado.
8. **PDFs com XFA, texto em curvas e criptografia com senha de usuário.** Não
   testados.
9. **Desempenho do OCR em 300 DPI.** Os testes usam 200 DPI para ganhar tempo; o
   padrão do aplicativo é 300 DPI.

## 8. Limite de interpretação destes resultados

A aprovação de um conjunto sintético **não é prova de segurança universal**. Os
documentos de teste foram construídos pelo mesmo raciocínio que construiu os
detectores, o que cria um viés inevitável: eles verificam que o programa faz o
que foi projetado para fazer, não que o projeto cubra tudo o que existe em
processos reais.

A validação independente embutida no aplicativo tem o mesmo limite: ela reutiliza
os detectores da análise, de modo que **a ausência de detecções não prova
anonimização integral**.

Recomenda-se, antes de qualquer uso profissional, uma bateria de validação
conduzida por equipe que não participou do desenvolvimento, primeiro com
documentos sintéticos próprios e depois com documentos reais em ambiente
controlado, conforme `docs/SEGURANCA.md`, seção 6.
