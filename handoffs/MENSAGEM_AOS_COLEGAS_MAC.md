# Mensagem para enviar junto com o pacote para Mac

Mesma estrutura de `MENSAGEM_AOS_COLEGAS.md` (versão Windows), trocando os
passos do Windows pelos do Mac. **Os avisos do final continuam não sendo
decorativos.**

---

## Versão curta (chat)

> Pessoal, há agora versão para **Mac** da ferramenta que prepara cópia
> anonimizada de processo em PDF — remove nome, CPF, endereço, telefone e
> afins, inclusive em documento digitalizado. Roda **tudo no computador
> local**, sem internet.
>
> Link: `<cole aqui>`
>
> Serve para Mac com chip Apple (M1 em diante) e macOS 15 ou mais novo. Abra o
> DMG e arraste o "Anonimizador DPU" para a pasta Aplicativos.
>
> **Na primeira abertura** o Mac vai dizer que não pôde verificar o programa.
> É porque ele não tem a assinatura paga da Apple, nada além disso. Clique em
> "Concluído", vá em **Ajustes do Sistema → Privacidade e Segurança**, role até
> "Segurança" e clique em **"Abrir Mesmo Assim"**. Só na primeira vez.
>
> Duas coisas importantes antes de usar:
>
> 1. É **versão de testes**. Ainda não passou pela homologação da STI. Usem
>    primeiro com documentos que não sejam sigilosos.
> 2. O programa remove o que ele encontra. **O que ele não encontra, passa** —
>    e nenhum relatório avisa sobre isso. Confiram o PDF final antes de
>    compartilhar com quem quer que seja.

---

## Versão para e-mail

**Assunto:** Anonimizador de processos para Mac (versão de testes)

Prezados colegas,

A ferramenta que prepara cópias anonimizadas de processos judiciais em PDF
ganhou versão para Mac, com o mesmo funcionamento da versão Windows.

**O que ela faz**

Localiza e remove dados pessoais — nomes, CPF, RG, endereço, CEP, telefone,
e-mail, número de benefício, entre outros —, substituindo-os por pseudônimos
que preservam a leitura da peça (`[ASSISTIDO_1]`, `[CPF_2]`). Funciona tanto em
PDF com texto quanto em documento digitalizado, por reconhecimento óptico. O
dado é **removido do arquivo**, e não apenas coberto por uma tarja.

Ao final, a ferramenta reabre o arquivo gerado e **confere o próprio trabalho**
por outro caminho, emitindo um veredito e um relatório auditável.

**Como instalar**

Requer Mac com chip Apple (M1 ou mais novo) e macOS 15 (Sequoia) ou mais
recente. Abra o arquivo `AnonimizadorDPU-mac.dmg` e arraste o "Anonimizador
DPU" para a pasta Aplicativos. Não é preciso ser administrador e nada é
baixado da internet: o reconhecimento óptico já vem dentro do programa.

Na primeira abertura, o macOS exibe o aviso de que não pôde verificar o
programa, porque ele não tem a assinatura digital paga da Apple. Para liberar:
clique em "Concluído", abra **Ajustes do Sistema → Privacidade e Segurança**,
role até a seção "Segurança" e clique em **"Abrir Mesmo Assim"**, confirmando
com a senha. Isso só é necessário uma vez. O arquivo `INSTALAR.txt`, dentro do
DMG, traz o passo a passo e o uso em três minutos.

**Privacidade**

Todo o processamento é local. Durante a execução, o acesso à rede é bloqueado
dentro do próprio processo — qualquer tentativa de conexão falha de forma
visível. Nenhum nome, CPF ou trecho dos autos é gravado em log, e os relatórios
gerados não contêm dados pessoais originais.

**O que peço**

Que usem **apenas com documentos não sigilosos** por enquanto, e relatem o que
encontrarem: dado que escapou, texto removido que não deveria ter sido,
qualquer comportamento estranho.

**O que preciso deixar claro**

Esta é uma versão de testes. Ela **não foi homologada** pela área de tecnologia
da DPU nem avaliada pela instância competente em proteção de dados.

A ferramenta remove o que consegue identificar. **O que ela não identifica
permanece no documento, e nenhum relatório avisa sobre isso.** A classificação
"APROVADO" significa apenas que os testes automáticos desta versão passaram —
não é certificado de anonimização.

Além disso, ela não trata a reidentificação por contexto: datas, uma doença
rara ou um detalhe do caso podem identificar a pessoa mesmo sem nenhum nome ou
CPF no texto.

**Por isso: confiram o documento final antes de qualquer uso, e não tratem o
resultado como automaticamente seguro.**

As limitações estão descritas em `documentacao/LIMITACOES.md`, no pacote.

Atenciosamente,

---

## Antes de enviar — conferir

- [ ] O link está acessível para quem vai receber?
- [ ] O destino é interno à DPU? (Sair da instituição muda a situação da
      licença AGPL — ver `LICENCAS.txt`.)
- [ ] A mensagem deixa claro que é versão de testes?
- [ ] A mensagem pede para não usar com documento sigiloso ainda?
- [ ] O pacote foi testado por **um** colega, em outro Mac, antes de ir para o
      grupo todo?
- [ ] A mensagem explica a liberação da primeira abertura ("Abrir Mesmo
      Assim")?
