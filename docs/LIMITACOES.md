# Limitações conhecidas

Lista deliberadamente honesta do que esta versão **não** resolve. Nenhum dos
itens abaixo é compensado por configuração: são limites reais da abordagem.

---

## 1. OCR

* **Qualidade da digitalização manda.** Documentos tortos, com baixo contraste,
  carimbos sobrepostos, fundo ruidoso, letra manuscrita ou fax de baixa
  resolução produzem leitura parcial ou errada. Um CPF presente na imagem pode
  simplesmente não ser lido — e, portanto, não será redigido.
* **Texto manuscrito não é reconhecido.** O Tesseract trabalha com texto
  impresso. Assinaturas, anotações à mão e preenchimentos manuscritos não são
  localizados por OCR; dependem de marcação manual de região pelo usuário.
* **Cobertura é uma métrica aproximada.** O aplicativo calcula a fração de
  palavras com confiança aceitável. Uma página pode atingir a cobertura mínima
  e ainda assim ter lido errado justamente o trecho que importa.
* **Idiomas.** Estão previstos português e português + inglês. Documentos em
  outros idiomas exigem o `traineddata` correspondente instalado.
* **Custo.** O OCR a 300 DPI é a etapa mais lenta; processos extensos levam
  minutos a horas.

## 2. Detecção de entidades

* **Nomes são heurística, não compreensão.** A detecção se apoia em
  capitalização, conectores, rótulos de contexto ("Requerente:", "Testemunha:")
  e num léxico local de prenomes, sobrenomes e vocabulário jurídico
  (`core/lexico_pt.py`). Consequências:
  * nomes sem rótulo e em meio a texto corrido podem passar;
  * nomes grafados integralmente em minúsculas não são detectados;
  * a palavra que abre a frase é descartada quando tem terminação verbal, o que
    reduz falsos positivos mas pode cortar o primeiro nome de uma pessoa cujo
    prenome termine em "-ado", "-ida" e semelhantes.
* **Caixa alta exige evidência — e isso tem um preço.** Em peça judicial, texto
  inteiramente em maiúsculas é quase sempre título de seção ("PODER
  JUDICIÁRIO", "REEXAME DE PROVA"), e não nome. Por isso uma sequência em caixa
  alta só é tratada como pessoa quando há rótulo processual por perto ou quando
  alguma palavra é prenome ou sobrenome conhecido.
  **Limite assumido:** um nome incomum, grafado em caixa alta e sem rótulo
  processual próximo, **não será detectado automaticamente**. Isso é uma troca
  deliberada: a versão anterior marcava dezenas de cabeçalhos por documento, e
  uma lista tomada por falsos positivos faz o revisor parar de ler — o que é
  pior do que a lacuna. Quem precisar do comportamento antigo pode acrescentar
  o nome em **termos personalizados**, na aba de categorias.
* **O léxico de nomes não é exaustivo.** Nenhuma lista de nomes é. Ele cobre os
  prenomes e sobrenomes mais usuais no Brasil e serve para **elevar** a
  confiança, nunca para rejeitar sozinho um candidato em caixa de título.
* **Medicamento não é pessoa, e isso é uma regra, não compreensão.** Nomes de
  medicamento deixam de ser tratados como nome por três caminhos: uma lista de
  princípios ativos frequentes, os sufixos de denominação genérica (`-mabe`,
  `-prazol`, `-sartana`) e o contexto ("uso contínuo de X"). Um medicamento
  fora desses três caminhos ainda pode aparecer como candidato — e uma pessoa
  cujo sobrenome termine como um medicamento pode ser descartada, embora o
  léxico de nomes tenha precedência justamente para evitar isso.
* **Não há modelo de linguagem por padrão.** O reconhecimento por modelo local
  (spaCy) é opcional e exige que o modelo já esteja instalado em disco. Sem ele,
  valem apenas as regras.
* **RG não tem padrão nacional.** Não existe dígito verificador uniforme nem
  formato único. A detecção depende integralmente do rótulo no texto, e um RG
  escrito sem rótulo não é encontrado.
* **Validar dígito verificador não prova nada sobre a pessoa.** Um CPF
  matematicamente válido pode ser fictício; um número inválido pode ser o CPF
  real de alguém, digitado com erro. Por isso números rotulados com dígito
  inválido são marcados como pendência em vez de descartados.
* **Dados sensíveis de saúde.** Só são detectados códigos CID rotulados.
  Diagnósticos escritos por extenso, histórico clínico, exames descritos em
  texto corrido e laudos não são identificados como dado sensível.
* **Endereços.** A detecção parte de palavras-chave de logradouro. Endereços
  escritos de forma atípica, ou referências indiretas ("na casa da irmã, no
  bairro X"), não são capturados. Palavras ambíguas — "Conjunto", "Setor",
  "Quadra", "Lote", "Bloco" — só valem como endereço quando há número no
  trecho, porque também são vocabulário jurídico ("CONJUNTO PROBATÓRIO").
  **Consequência:** um endereço que use essas palavras sem número por perto
  passa despercebido.
* **Localidade exige rótulo.** Cidade, estado e comarca são detectados — podem
  identificar a pessoa — mas **só quando há rótulo que os ligue a alguém**:
  "ESTADO DE…", "MUNICÍPIO DE…", "COMARCA DE…", "natural de…", "residente
  em…". Uma menção genérica ("São Paulo e Minas Gerais são unidades
  federativas") **não** é detectada, porque ali não há pessoa a proteger e
  anonimizar só destruiria o texto. **Consequência:** um lugar que identifique
  a pessoa sem nenhum desses rótulos passa despercebido.
* **Lugar não recebe papel processual.** Em "REQUERIDO: ESTADO DE SANTA
  CATARINA", o requerido é o Estado, não a localidade. Por isso a localidade
  recebe pseudônimo `[LOCAL_n]`, e nunca `[REQUERIDO_n]`. A contrapartida é que
  a ferramenta **não** identifica a pessoa jurídica como parte: ela trata o
  nome do lugar, e o restante da expressão permanece no texto.
* **Endereço cortado na quebra de linha.** O trecho de endereço não atravessa
  quebra de linha. Em PDF, "Rua das Palmeiras, 150, Jardim / Aurora" pode ser
  capturado só até "Jardim". O CEP, quando presente, é detectado à parte.
* **Profissionais são mantidos por pessoa, não por ocorrência.** Se um nome
  aparece com papel de profissional (advogado, defensor, magistrado, perito ou
  servidor) em **qualquer** ponto do documento, nenhuma de suas ocorrências é
  redigida — inclusive as que aparecem sem rótulo. Redigir só algumas deixaria
  o nome legível no arquivo e tornaria a redação inútil. **Consequência:** se
  uma pessoa for ao mesmo tempo parte e profissional no mesmo documento, ela
  será tratada como profissional e **não** será anonimizada. Essas ocorrências
  aparecem na revisão desmarcadas, com o motivo à vista, e podem ser marcadas
  à mão.
* **Pessoas relacionadas.** Familiares, testemunhas e terceiros só são tratados
  quando seus nomes aparecem de forma reconhecível. Relações descritas sem nome
  ("a filha mais velha") são preservadas — e podem identificar alguém.

## 3. Assinaturas e certificados

* Alterar o documento **invalida** a assinatura digital. Não há como redigir
  conteúdo e manter a assinatura válida; o aplicativo não tenta e não promete.
* Assinaturas manuscritas digitalizadas são imagens: o aplicativo pode sugerir
  áreas prováveis, mas a decisão e a marcação são do usuário.
* Carimbos e selos de tribunais podem conter números identificadores em forma
  gráfica não lida pelo OCR.

## 4. PDFs complexos

* **Portfólios PDF** (coleções de documentos) não têm o conteúdo interno
  processado. Bloqueiam a aprovação.
* **Camadas de conteúdo opcional (OCG)** não são desmontadas. Conteúdo oculto em
  camada pode não aparecer na conferência visual. Bloqueiam a aprovação; a
  alternativa é reconstruir a página por renderização, com as perdas
  correspondentes.
* **PDFs malformados ou reparados na leitura** podem ter objetos não
  interpretados integralmente. Bloqueiam a aprovação.
* **PDFs protegidos por senha** não são processados.
* **Texto em contornos vetoriais** (texto convertido em curvas) não é extraível
  nem reconhecido por OCR confiável.
* **Objetos de formulário XFA** e estruturas proprietárias não são tratados.
* **Páginas muito grandes** podem exceder o limite de renderização; nesse caso a
  página fica sem cobertura e impede a aprovação.

## 5. Anexos

* Apenas PDFs incorporados seriam analisáveis — e esta versão **não** processa o
  conteúdo de nenhum anexo.
* Planilhas, imagens, documentos de texto e arquivos binários incorporados são
  inventariados e, por padrão, removidos; o relatório registra que o conteúdo
  **não foi examinado**.
* Se o usuário optar por mantê-los, o documento não pode ser aprovado.

## 6. Reidentificação por contexto

Este é o limite mais importante e o menos visível.

Mesmo com todos os identificadores diretos removidos, uma pessoa pode ser
reidentificada pela combinação de: datas, doença rara, local de trabalho,
composição familiar, sequência de fatos narrada, valores de benefício, nomes de
instituições e quaisquer particularidades do caso.

A ferramenta **não mede nem reduz** esse risco. Nenhuma métrica de
k-anonimato ou equivalente é calculada. Um documento classificado como
"APROVADO NOS TESTES AUTOMATIZADOS" pode, ainda assim, permitir reidentificação.

## 6-A. O que a aprovação deixou de garantir

A partir da versão em que o padrão passou a ser **remover tudo que foi
detectado**, com o revisor desmarcando o que deve permanecer, o significado da
classificação "APROVADO NOS TESTES AUTOMATIZADOS" mudou em um ponto:

* **Antes**, nenhuma ocorrência era removida sem decisão humana explícita, e
  qualquer item não decidido bloqueava a aprovação. A aprovação implicava, na
  prática, que alguém havia passado por todas as linhas.
* **Agora**, nada fica aguardando decisão: tudo já entra decidido (sai). O
  bloqueio por "ocorrências pendentes" continua no código e vale quando uma
  pendência é criada, mas **a aprovação não atesta mais que um humano
  examinou cada ocorrência**.

A troca foi deliberada e tem uma lógica de segurança: o padrão agora falha para
o lado seguro. No modelo anterior, a desatenção **deixava dado pessoal no
documento**; neste, a desatenção apenas remove conteúdo a mais. O primeiro erro
é vazamento, o segundo é perda de legibilidade.

O que continua bloqueando a aprovação — e é o que de fato importa:

* página não examinada (sem texto e sem OCR com cobertura suficiente);
* ocorrência sem área determinada, que não pode ser redigida;
* anexo não tratado, assinatura digital, camadas de conteúdo, portfólio;
* identificador original ainda recuperável no arquivo de saída.

Quem precisar da garantia anterior deve desligar **"Marcar tudo para remoção
por padrão"** na aba de categorias, e a exigência de decisão item a item volta
a valer.

## 7. Limites da validação automática

* A validação usa **os mesmos detectores** da análise. Aquilo que a detecção não
  enxerga, a validação também não enxerga. **Ausência de resultado não é prova
  de anonimização.**
* A conferência de áreas verifica se o valor original deixou de ser extraível
  naquela região e se a área redigida ficou visualmente uniforme; ela não
  interpreta o restante da página.
* A busca por identificadores conhecidos cobre apenas o que foi **confirmado**
  na sessão. Dados rejeitados pelo usuário como falso positivo não são
  procurados.
* A validação não detecta vazamento por estruturas que ela própria não examina.

## 8. Desempenho

* O processamento é sequencial, documento a documento e página a página. Não há
  paralelismo entre páginas nesta versão.
* Processos com milhares de páginas digitalizadas podem levar horas.
* A interface permanece responsiva (o trabalho roda em segundo plano) e a
  operação pode ser cancelada, mas o progresso parcial não é aproveitável: um
  documento cancelado é sempre REPROVADO.
* O estado da revisão não é salvo entre execuções: fechar o aplicativo descarta
  as decisões (opção deliberada, para não gravar dados sigilosos em disco).

## 9. Interface

* O visualizador de páginas é simples: exibe a página e as áreas, sem zoom
  contínuo nem navegação página a página independente da lista de ocorrências.
* A marcação manual de região aplica-se à página da ocorrência selecionada.
* Não há desfazer/refazer das decisões de revisão.

## 10. Plataforma

* Testado em Windows 11 com Python 3.13.13 e Tesseract 5.5. O funcionamento em
  Windows 10 é esperado, mas **não foi verificado** nesta máquina.
* O executável gerado pelo PyInstaller **não foi testado** neste ambiente (ver
  `docs/TESTES.md`, seção "Testes não executados").
