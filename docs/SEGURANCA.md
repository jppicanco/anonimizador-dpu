# Segurança

Este documento descreve o que a ferramenta **garante de fato**, o que ela
**não** garante e como as falhas são tratadas. Nenhuma afirmação aqui deve ser
lida como promessa de anonimização infalível.

---

## 1. Garantias reais (verificadas por teste automatizado)

### 1.1 Processamento local e ausência de transmissão

Durante a inspeção, a análise e o processamento, o acesso à rede é **bloqueado
dentro do processo**: `socket.socket`, `socket.create_connection` e
`socket.getaddrinfo` são substituídos por funções que levantam
`AcessoRedeBloqueado` (`core/security.py`, `rede_bloqueada`). O bloqueio vale
para qualquer biblioteca, inclusive de terceiros, e é restaurado ao final,
mesmo em caso de exceção.

Testes: `tests/test_security.py::TestBloqueioDeRede` e
`tests/test_end_to_end.py::test_processamento_nao_usa_rede` (verifica que
**nenhum socket é aberto** em um processamento completo).

A existência de conexão disponível na máquina não autoriza o programa a
utilizá-la: não há nenhuma rotina de telemetria, atualização automática ou
envio de conteúdo.

### 1.2 O arquivo original nunca é alterado

* A entrada é aberta apenas para leitura; a redação trabalha sobre uma **cópia**
  em diretório temporário com permissões restritas (`0o700`).
* `destino_seguro()` recusa um caminho de saída que coincida com o original.
* Havendo arquivo de mesmo nome no destino, é gerado um nome alternativo, salvo
  autorização explícita de sobrescrita na interface.

Testes: `tests/test_security.py::TestProtecaoDoOriginal` e
`test_redaction_engine.py::test_original_permanece_intacto` (compara o SHA-256
antes e depois).

### 1.3 A redação remove o conteúdo

O texto é retirado do fluxo de conteúdo da página
(`PDF_REDACT_TEXT_REMOVE`) e os pixels correspondentes nas imagens são
substituídos (`PDF_REDACT_IMAGE_PIXELS`). A verificação não se limita à
aparência: `test_conteudo_removido_tambem_do_fluxo_interno` inspeciona os
*streams* do PDF gravado e falha se o valor original ainda estiver lá.

### 1.4 Validação independente do resultado

O arquivo gravado é fechado, reaberto e reexaminado por um caminho de código
distinto do que executou a redação: reextração de texto, OCR de verificação,
conferência de cada área redigida, exame de metadados, anexos e camadas, e
busca pelos identificadores originais conhecidos da sessão.

### 1.5 Bloqueios que não podem ser contornados

Não existe botão que libere um documento com falha crítica. A classificação
final é decidida em `output_validator.decidir_veredito`, e a opção
`permitir_aprovacao_com_ressalvas` alcança **apenas** riscos de severidade
*aviso*. Teste: `test_output_validator.py::TestDecisaoDeVeredito::test_bloqueio_critico_nunca_vira_ressalva`.

### 1.6 Minimização de dados nos registros

* O relatório (JSON e HTML) nunca contém CPF, nome, endereço, trechos dos autos
  ou o texto extraído. Cada ocorrência aparece com categoria, página, origem,
  confiança, situação, pseudônimo, **valor mascarado** e um hash salgado por
  sessão. Teste: `test_report_generator.py::test_relatorio_nao_contem_dados_pessoais`.
* O log aplica um filtro que mascara CPF, CNPJ, número de processo, e-mail, CEP
  e telefone antes de qualquer gravação (`core/audit_logger.py`).
* A inspeção lista apenas as **chaves** dos metadados, nunca os seus valores.
* O mapa pseudônimo → valor original existe só em memória e, por padrão, **não é
  gerado**. `tabela_reversao()` devolve vazio sem autorização explícita.

### 1.7 Limites operacionais

Configuráveis em `config.limites`: tamanho máximo do arquivo (padrão 500 MB),
número máximo de páginas (3000), tempo máximo por documento (2 h) e dimensão
máxima de renderização (10000 px). Entradas sem assinatura `%PDF`, com extensão
diferente de `.pdf`, com caractere nulo no caminho ou que sejam links
simbólicos são recusadas.

### 1.8 Menor privilégio

O aplicativo roda com a conta do usuário, não exige administrador, não altera
configurações de segurança do Windows, não registra serviços e não acessa
e-mail, nuvem, navegador ou sistemas institucionais.

### 1.9 Arquivos incorporados nunca são executados

Anexos são apenas inventariados (nome, tamanho, tipo). Por padrão são removidos
do documento de saída, e o relatório registra que o **conteúdo deles não foi
analisado**. Se forem mantidos por configuração, tornam-se pendência que
impede a aprovação.

---

## 2. Dados temporários

* A cópia de trabalho e os arquivos intermediários ficam em um diretório
  temporário criado com `mkdtemp` e permissões `0o700`, removido ao final da
  operação, inclusive em caso de exceção.
* A renderização das páginas para OCR ocorre **em memória**, página a página;
  imagens não são gravadas em disco e não são mantidas todas simultaneamente.

> **Limite documentado:** apagar arquivos em disco SSD **não garante eliminação
> física irrecuperável**. A remoção dos temporários é lógica. Se o modelo de
> ameaça exigir destruição efetiva, isso depende de medidas de sistema
> (criptografia de disco, por exemplo) fora do alcance desta ferramenta.

---

## 3. Metadados e estruturas internas

Tratados: metadados padrão, XMP, anotações, campos de formulário, links,
marcadores, arquivos incorporados, JavaScript, texto oculto, miniaturas e
campos redefiníveis (via `Document.scrub`).

**Não desmontados nesta versão:** camadas de conteúdo opcional (OCG). Quando
existem, a aprovação é bloqueada e o aplicativo oferece a reconstrução da página
por renderização, que elimina as camadas ao custo de perder texto selecionável,
links e formulários.

### Assinaturas digitais

Qualquer alteração invalida a assinatura. A ferramenta **detecta** a assinatura,
**informa** o usuário, **bloqueia** a aprovação automática e **não promete**
preservar validade alguma.

---

## 4. Tratamento de falhas

| Situação | Comportamento |
|---|---|
| PDF malformado | Erro controlado, risco crítico, documento não aprovado; o lote continua. |
| PDF protegido por senha | Recusado com mensagem explícita. |
| Página ilegível | Marcada como não examinada; impede a aprovação. |
| OCR indisponível | Registrado como risco crítico; páginas com imagem ficam sem cobertura e o documento não é aprovado. |
| Ocorrência confirmada sem área segura | **Não é redigida no palpite**: vira falha crítica e bloqueia a página. |
| Falha ao aplicar a redação | Ocorrências da página viram falha crítica; veredito REPROVADO. |
| Identificador original ainda recuperável | Veredito REPROVADO. |
| Cancelamento | Encerramento controlado; relatório marcado como cancelado; veredito REPROVADO; original intacto. |
| Exceção inesperada em segundo plano | Capturada no *worker*, exibida ao usuário, sem travar a interface. |

---

## 5. Riscos residuais relevantes

1. **Falso negativo de detecção.** Um dado pessoal em forma não prevista
   (apelido, descrição, número sem rótulo) não é detectado. A validação
   independente usa os **mesmos** detectores, portanto também não o encontra:
   ausência de resultado não prova anonimização.
2. **Reidentificação por contexto.** Datas, narrativa clínica, relações
   familiares e sequência de fatos podem identificar uma pessoa mesmo sem
   qualquer identificador direto. A ferramenta não trata isso.
3. **OCR imperfeito.** Caracteres lidos errado podem impedir a detecção de um
   CPF presente na imagem. A métrica de cobertura mitiga, mas não elimina.
4. **Conteúdo em formatos não processados.** Anexos não-PDF, portfólios e
   objetos exóticos não são analisados — por isso bloqueiam a aprovação.
5. **A máquina do usuário.** O arquivo anonimizado, os relatórios e os
   temporários residem no computador local. A proteção desse ambiente é
   responsabilidade do usuário e da instituição.
6. **Destino posterior do arquivo.** A ferramenta não envia nada a lugar algum;
   o envio do PDF anonimizado a qualquer ferramenta de IA é um ato posterior,
   humano, sujeito às normas da DPU.

---

## 6. Pendências para validação institucional

Antes de qualquer uso com processos sigilosos, as seguintes questões precisam
de deliberação da área de tecnologia e da instância competente da DPU:

1. **Política de anonimização**: quais categorias são obrigatórias; se
   advogados, defensores, magistrados, peritos e servidores devem ser
   anonimizados (hoje, não, por padrão).
2. **Resultado "APROVADO COM RESSALVAS"**: se a política institucional o admite
   (hoje desabilitado).
3. **Tabela de reversão**: se pode existir, em que suporte e sob qual controle
   (hoje nunca é gerada).
4. **Licenciamento**: o PyMuPDF é AGPL-3.0; a forma de distribuição interna
   precisa de análise jurídica (ver README, seção 11).
5. **Retenção**: por quanto tempo os PDFs anonimizados e os relatórios podem
   ser mantidos, e onde.
6. **Validação independente**: conveniência de auditoria por equipe que não
   participou do desenvolvimento, com documentos sintéticos e, depois, com
   documentos reais em ambiente controlado.
7. **Uso posterior por ferramentas de IA**: a decisão sobre enviar o documento
   anonimizado a qualquer serviço de IA é institucional e está fora do escopo
   técnico desta ferramenta.
