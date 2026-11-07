# Manual do usuário

Aplicativo: **Anonimizador DPU** — preparação local de cópias anonimizadas de
processos judiciais em PDF.

> A aprovação automatizada **não garante anonimização integral** e **não
> substitui** a sua revisão nem a avaliação de conformidade com as normas da
> DPU. Leia também `docs/LIMITACOES.md`.

---

## 1. Antes de começar

1. Confirme o ambiente:

   ```bat
   python scripts\verificar_ambiente.py
   ```

   Se o OCR aparecer como indisponível, instale o Tesseract com o idioma
   português antes de prosseguir (README, seção 3.1). Sem OCR, páginas
   digitalizadas **não** são examinadas e o documento nunca será aprovado.

2. Abra o aplicativo:

   ```bat
   python -m anonimizador_dpu.app.main
   ```

A janela tem cinco abas numeradas, na ordem em que devem ser percorridas. O
aviso em destaque no topo permanece visível o tempo todo.

---

## 2. Etapa 1 — Documentos

1. **Adicionar PDFs…** — selecione um ou vários arquivos do mesmo processo. A
   ordem da lista é preservada no processamento em lote.
2. **Selecionar pasta de saída…** — escolha uma pasta **diferente** da pasta dos
   originais. O aplicativo nunca sobrescreve o arquivo de entrada; o resultado
   recebe o sufixo `_ANONIMIZADO`.
3. Se já existir arquivo de mesmo nome no destino, um nome alternativo é gerado
   automaticamente, salvo se você marcar a opção de sobrescrita.
4. Confira a linha de estado do OCR no rodapé da aba.
5. Clique em **Inspecionar documentos ▶**.

## 3. Etapa 2 — Inspeção

A aba mostra, por documento: número de páginas e sua classificação (texto,
digitalizada, híbrida, vazia), metadados preenchidos, presença de formulário,
anotações, links, arquivos incorporados, camadas, assinaturas digitais,
marcadores e o SHA-256 do arquivo de entrada.

Abaixo vem a **lista de riscos estruturais**. Riscos em vermelho marcados como
*bloqueia a aprovação* significam que, mesmo com a redação perfeita, o documento
**não** poderá ser classificado como aprovado — é o caso de anexos, assinaturas
digitais, camadas de conteúdo e páginas ilegíveis.

Leia essa lista antes de prosseguir. Se houver anexos relevantes, considere
tratá-los separadamente.

Clique em **Extrair texto, executar OCR e detectar dados ▶**.

## 4. Etapa 3 — Categorias (pode ser ajustada antes da análise)

Marque as categorias que a sua política exige anonimizar, agrupadas de A a H.
Ajuste também:

* **Anonimizar profissionais** — advogados, defensores, magistrados, peritos e
  servidores. Desligado por padrão: normalmente esses nomes são públicos e a sua
  remoção prejudica a compreensão jurídica. Decisão institucional.
* **Modo de redação** —
  *Pseudônimo* (recomendado): remove o dado e escreve `[ASSISTIDO_1]`,
  `[CPF_2]` etc. no lugar, preservando a leitura.
  *Tarja sólida*: remove o dado e deixa a área preenchida, sem rótulo.
* **Confiança mínima para confirmação automática** (padrão 90%) — acima disso,
  ocorrências inequívocas já entram confirmadas, evitando revisão item a item do
  que é trivial.
* **Abaixo desta confiança, decisão humana obrigatória** (padrão 70%).
* **Idiomas e resolução do OCR**.

### 4.1 Termos da sua unidade

Dois campos, no fim da aba, um termo por linha:

* **Sempre remover** — nomes e expressões que devem sair mesmo que a detecção
  automática não os encontre. Use para o nome incomum que a heurística não
  reconhece.
* **Nunca remover** — expressões que não devem ser tratadas como dado pessoal.
  Use para eliminar falso positivo recorrente na sua matéria.

A ferramenta já ignora o vocabulário jurídico corrente ("poder judiciário",
"reexame de prova", "conjunto probatório"), nomes de recurso, nomes de sistema
e nomes de medicamento — nada disso identifica pessoa. Se ainda assim aparecer
algo da sua área que não deveria, acrescente aqui em vez de rejeitar linha a
linha a cada documento.

Use **Salvar configuração** para preservar as escolhas entre sessões.

## 5. Etapa 4 — Revisão

Esta é a etapa que determina a qualidade do resultado.

### 5.0 O padrão é remover

**Tudo que foi detectado já entra marcado para remoção.** A caixa na primeira
coluna vem marcada, e marcada significa: esta ocorrência sai do documento.

Para **manter** alguma coisa no texto, desmarque a caixa daquela linha. Para
desmarcar várias de uma vez, selecione as linhas (Ctrl+A seleciona todas as
exibidas) e use **Desmarcar selecionadas (manter no texto)**.

A razão de o padrão ser esse: ele falha para o lado seguro. Esquecer de
desmarcar remove algo a mais do documento; esquecer de confirmar deixaria um
dado pessoal dentro dele. O primeiro erro custa legibilidade, o segundo custa
sigilo.

A coluna **Confiança** tem cor própria e é o que orienta a leitura:

| Cor | Significado |
|---|---|
| Verde | Confiança alta: formato inequívoco ou rótulo explícito. |
| Âmbar | Confiança média: confira antes de deixar sair. |
| Laranja | Confiança baixa: a detecção pode estar errada — vale olhar. |

Quem preferir o fluxo inverso — confirmar item a item, em vez de desmarcar —
pode desligar **"Marcar tudo para remoção por padrão"** na aba 3.

A **pasta de saída** pode ser escolhida aqui mesmo, no rodapé da aba, sem
voltar à etapa 1. Se você clicar em processar sem ter escolhido, o próprio
aviso oferece a escolha.

### 5.0.1 Lugar não é pessoa

Cidade, estado e comarca aparecem na categoria **"Cidade / estado / comarca"**
e recebem pseudônimo `[LOCAL_1]`, `[LOCAL_2]`. Eles são detectados porque podem
identificar a pessoa, mas **não recebem papel processual**: em "REQUERIDO:
ESTADO DE SANTA CATARINA" o requerido é o Estado, e chamar "Santa Catarina" de
`[REQUERIDO_1]` estaria errado.

A detecção só ocorre quando há rótulo ligando o lugar a alguém — "ESTADO DE",
"COMARCA DE", "natural de", "residente em". Menção genérica a um estado no meio
de uma fundamentação jurídica não é tocada.

> **O que "aprovado" passou a significar.** Como nada fica aguardando decisão,
> o bloqueio por "ocorrências pendentes" praticamente não é acionado. Ele
> continua existindo e vale quando alguém deixa uma pendência em aberto, mas a
> aprovação **não** atesta mais que um humano olhou linha a linha. Continuam
> bloqueando a aprovação, e esses são os que importam: página não examinada,
> área não determinada, anexo não tratado, assinatura digital e camadas de
> conteúdo.

### 5.1 Leitura da tabela

Cada linha é uma ocorrência, com: documento, página, categoria, origem (texto,
OCR, texto e OCR, anotação, formulário, metadado, manual), confiança, situação,
pseudônimo, valor mascarado, trecho minimizado, número de áreas e observação.

As situações são distintas e coloridas:

| Situação | Significado |
|---|---|
| Detectado | Encontrado, aguardando a sua decisão. |
| Confirmado para redação | Será removido. |
| Rejeitado (falso positivo) | Não será removido. |
| Pendente de decisão | Confiança baixa ou área incerta: **exige** decisão. |
| Redigido | Já removido no arquivo de saída. |
| Verificado | Removido e confirmado pela validação independente. |
| Falha crítica | A redação não pôde ser aplicada com segurança. |

> A coluna **Áreas** mostrando "sem área" significa que não foi possível
> determinar com segurança onde o dado está na página. Essas ocorrências **não
> são redigidas** e impedem a aprovação — trate-as marcando a região
> manualmente.

### 5.2 Decisões

* **Confirmar para redação** / **Rejeitar (falso positivo)** — valem para todas
  as linhas selecionadas.
* **Aplicar a equivalentes…** — aplica a decisão a todas as ocorrências da
  mesma entidade, em todos os documentos do lote, após confirmação.
* **Alterar categoria…** — corrige uma classificação errada (por exemplo, um
  número marcado como RG que na verdade é matrícula).
* **Separar pessoa homônima…** — quando duas pessoas diferentes têm o mesmo
  nome, selecione a ocorrência da segunda pessoa e separe-a: ela passa a ter
  pseudônimo próprio.
* **Marcar região na página** — selecione uma ocorrência da página desejada
  (para exibi-la à direita), clique no botão e **arraste** sobre a área a
  remover. Use para assinaturas manuscritas, fotografias, carimbos e qualquer
  conteúdo que o OCR não alcança.

### 5.3 Exibição dos valores originais

Por padrão a tabela mostra apenas valores mascarados e o trecho com o dado
substituído pela categoria. Marque **Exibir valores originais** somente quando
precisar decidir sobre uma ocorrência duvidosa, e apenas em ambiente adequado.

### 5.4 Filtros úteis

* Situação **Pendente de decisão** — mostra o que falta decidir.
* Categoria específica — para revisar em bloco, por exemplo, todos os nomes.

Quando não restar nenhuma ocorrência pendente, clique em
**Aplicar redação, validar e gerar relatório ▶**. Se ainda houver pendências, o
aplicativo avisa que elas **não serão redigidas** e que impedirão a aprovação.

## 6. Etapa 5 — Resultado

O resultado traz, por documento, a classificação em destaque:

| Classificação | O que significa |
|---|---|
| **APROVADO NOS TESTES AUTOMATIZADOS** | Todos os testes definidos passaram, sem pendências conhecidas. Não é garantia de anonimização integral. |
| **APROVADO COM RESSALVAS** | Só aparece se a política institucional admitir; as ressalvas estão listadas. |
| **REVISÃO OBRIGATÓRIA** | Há pendências, páginas sem cobertura ou riscos a resolver. |
| **REPROVADO** | Falha crítica, conteúdo identificador residual ou estrutura relevante não tratada. |

Abaixo vêm as áreas redigidas, os metadados removidos, as estruturas não
tratadas, o SHA-256 da saída, os números da validação e as pendências.

Os relatórios técnicos são gravados ao lado do arquivo de saída:
`…_ANONIMIZADO_relatorio.json` e `…_ANONIMIZADO_relatorio.html`.

**Abrir pasta de saída** abre o Explorador de Arquivos na pasta — o aplicativo
nunca envia o documento a outro programa automaticamente.

---

## 7. Como interpretar os relatórios

* **Cobertura do exame** — quantas páginas foram examinadas por texto e por OCR,
  e quais não foram examinadas integralmente. Página não examinada é página
  sobre a qual **nada se sabe**.
* **Ocorrências** — total, por categoria e por situação. Compare "confirmadas"
  com "redigidas" e "verificadas": diferenças indicam falhas.
* **Identificadores originais ainda recuperáveis** — tem de ser **zero**.
  Qualquer número acima de zero reprova o documento.
* **Estruturas NÃO tratadas** — leia sempre. É a lista do que ficou de fora.
* **Riscos e pendências** — a coluna "bloqueia aprovação" indica o que impede a
  classificação como aprovado.
* **SHA-256** — permite demonstrar depois que o arquivo conferido é exatamente
  aquele que foi validado.

O relatório **não** contém dados pessoais originais: ele serve para auditoria,
não para guardar conteúdo sigiloso.

---

## 8. Como lidar com falhas

| O que aconteceu | O que fazer |
|---|---|
| "OCR local indisponível" | Instale o Tesseract com `por.traineddata` e reabra o aplicativo. Não processe páginas digitalizadas sem OCR. |
| Página ilegível para OCR | Reescaneie com melhor qualidade, ou marque manualmente as áreas sensíveis da página, ou exclua a página do material a ser compartilhado. |
| "Ocorrência sem área determinada" | Marque a região manualmente na página correspondente e confirme. |
| Documento com assinatura digital | Decida se o uso justifica perder a assinatura. A cópia anonimizada nunca manterá a assinatura válida. |
| Documento com anexos | Extraia e trate os anexos separadamente, ou aceite que o documento não será aprovado. |
| Camadas de conteúdo opcional | Autorize a reconstrução das páginas por renderização, ciente da perda de texto selecionável e links. |
| PDF malformado | Reobtenha o arquivo da fonte original. |
| Veredito REPROVADO | **Não utilize o arquivo.** Leia as pendências, corrija a revisão e processe novamente. |
| Processamento cancelado | O arquivo de saída existe, mas está incompleto. Descarte-o e processe de novo. |
| Aplicativo fechado por engano | As decisões da revisão não são salvas (opção deliberada). Recomece a partir da inspeção. |

---

## 9. Boas práticas

1. **Valide primeiro com documentos sintéticos.** Gere-os com
   `python scripts\gerar_fixtures.py` e percorra o fluxo inteiro.
2. **Confira visualmente o PDF de saída** antes de qualquer uso, especialmente
   nas páginas digitalizadas.
3. **Nunca trate "APROVADO" como garantia.** É o resultado dos testes desta
   versão, não um certificado de anonimização.
4. **Pense na reidentificação por contexto.** Datas, doenças raras e detalhes do
   caso podem identificar a pessoa mesmo sem nenhum identificador direto.
5. **Guarde o relatório** junto com o arquivo anonimizado; ele documenta o que
   foi feito sem reproduzir dados sigilosos.
6. **Trate o PDF anonimizado como documento sensível** até que sua adequação
   tenha sido confirmada.
