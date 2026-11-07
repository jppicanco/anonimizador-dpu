# Mensagem para enviar junto com o pacote

Dois textos: um curto, para WhatsApp ou chat, e um para e-mail.
Ajuste o que quiser — mas **os avisos do final não são decorativos**. Eles são
o que separa "ferramenta útil" de "responsabilidade sua quando algo vazar".

---

## Versão curta (chat)

> Pessoal, montei uma ferramenta que prepara cópia anonimizada de processo em
> PDF — remove nome, CPF, endereço, telefone e afins, inclusive em documento
> digitalizado. Roda **tudo no computador local**, sem internet e sem instalação.
>
> Link: `<cole aqui>`
>
> **Ao baixar:** antes de descompactar, clique com o botão direito no ZIP,
> "Propriedades", e marque a caixa **"Desbloquear"**, se ela aparecer. Isso
> evita uma fila de avisos do Windows depois. Na primeira execução, se
> aparecer a tela azul "O Windows protegeu o computador", é só clicar em
> "Mais informações" → "Executar assim mesmo" — é um programa sem assinatura
> digital comercial, nada além disso.
>
> Duas coisas importantes antes de usar:
>
> 1. É **versão de testes**. Ainda não passou pela homologação da STI. Usem
>    primeiro com documentos que não sejam sigilosos.
> 2. O programa remove o que ele encontra. **O que ele não encontra, passa** —
>    e nenhum relatório avisa sobre isso. Confiram o PDF final antes de
>    compartilhar com quem quer que seja.
>
> Deu problema ou ficou estranho? Me avisem, que eu ajusto.

---

## Versão para e-mail

**Assunto:** Anonimizador de processos (versão de testes) — pedido de avaliação

Prezados colegas,

Desenvolvi uma ferramenta que prepara cópias anonimizadas de processos
judiciais em PDF e gostaria de submetê-la à avaliação de vocês antes de
qualquer uso mais amplo.

**O que ela faz**

Localiza e remove dados pessoais — nomes, CPF, RG, endereço, CEP, telefone,
e-mail, número de benefício, entre outros —, substituindo-os por pseudônimos
que preservam a leitura da peça (`[ASSISTIDO_1]`, `[CPF_2]`). Funciona tanto em
PDF com texto quanto em documento digitalizado, por reconhecimento óptico. O
dado é **removido do arquivo**, e não apenas coberto por uma tarja: quem abrir o
PDF e selecionar o texto não encontra nada embaixo.

Ao final, a ferramenta reabre o arquivo gerado e **confere o próprio trabalho**
por outro caminho, emitindo um veredito e um relatório auditável.

**Como usar**

Descompacte o arquivo e clique em `aplicativo\AnonimizadorDPU.exe`. Não há
instalação, não é preciso ser administrador e nada é baixado da internet. O
arquivo `INSTALAR.txt` explica o fluxo em três minutos.

Dois detalhes do Windows que poupam tempo: **antes de descompactar**, clique
com o botão direito no ZIP, abra "Propriedades" e marque a caixa
"Desbloquear", se ela estiver lá — todo arquivo baixado chega marcado como
"de outro computador", e a marca se propaga para o conteúdo. E, na primeira
execução, o Windows pode exibir a tela "O Windows protegeu o computador":
clique em "Mais informações" e em "Executar assim mesmo". Isso ocorre porque
o executável não tem assinatura digital comercial, não porque haja algo de
errado com ele.

**Privacidade**

Todo o processamento é local. Durante a execução, o acesso à rede é bloqueado
dentro do próprio processo — qualquer tentativa de conexão falha de forma
visível. Nenhum nome, CPF ou trecho dos autos é gravado em log, e os relatórios
gerados não contêm dados pessoais originais.

**O que peço**

Que usem **apenas com documentos não sigilosos** por enquanto, e me relatem o
que encontrarem: dado que escapou, texto removido que não deveria ter sido,
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

As limitações estão descritas em `documentacao/LIMITACOES.md`, no pacote. É
leitura curta e vale a pena.

Atenciosamente,

---

## Antes de enviar — conferir

- [ ] O link está acessível para quem vai receber?
- [ ] O destino é interno à DPU? (Sair da instituição muda a situação da
      licença AGPL — ver `LICENCAS.txt`.)
- [ ] A mensagem deixa claro que é versão de testes?
- [ ] A mensagem pede para não usar com documento sigiloso ainda?
- [ ] O pacote foi testado por **um** colega, em outra máquina, antes de ir
      para o grupo todo?
- [ ] A mensagem explica o "Desbloquear" do ZIP e o aviso do SmartScreen?
