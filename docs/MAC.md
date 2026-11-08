# Anonimizador DPU para Mac

Versão para macOS do mesmo aplicativo: **mesmo código, mesmas etapas, mesma
detecção, mesma validação**. O que muda é só o necessário para o programa
funcionar e caber na tela do Mac, listado abaixo com o porquê.

## Requisitos

| | |
|---|---|
| Processador | Mac com chip Apple (M1 ou mais novo). Macs Intel não são atendidos. |
| Sistema | macOS 15 (Sequoia) ou mais recente. |
| Instalação | Arrastar o aplicativo para a pasta Aplicativos. Sem administrador, sem Homebrew, sem internet. |
| OCR | Tesseract 5.5.4 **embutido** no aplicativo, com português, inglês e detecção de orientação. |

O passo a passo para quem recebe o pacote está em
`scripts/mac/pacote/INSTALAR-mac.txt` (vai no DMG como `INSTALAR.txt`),
inclusive a liberação da primeira abertura: o aplicativo não tem a assinatura
paga da Apple (Developer ID + notarização), e o macOS exige que o usuário o
libere uma vez em *Ajustes do Sistema > Privacidade e Segurança > Abrir Mesmo
Assim*.

## Conferência no próprio aplicativo

O executável de dentro do pacote aceita `--verificar`, que faz no aplicativo
pronto o que `scripts/verificar_ambiente.py` faz a partir do código-fonte:

```bash
"/Applications/Anonimizador DPU.app/Contents/MacOS/AnonimizadorDPU" --verificar
```

Confere o OCR embutido e o bloqueio de rede e processa de ponta a ponta dois
PDFs fictícios (um com texto e um digitalizado), sem abrir janela, em pasta
temporária. Termina com "Aplicativo pronto para uso." e código de saída 0.

## O que mudou em relação à versão Windows

### No código do aplicativo (todas as mudanças só valem no Mac)

| Arquivo | Mudança | Por quê |
|---|---|---|
| `core/config.py` | Procura o Tesseract embutido também em `sys._MEIPASS/tesseract/tesseract` e em `/opt/homebrew/bin`; nome do executável sem `.exe` fora do Windows | No `.app`, o PyInstaller guarda o que foi embutido em `Contents/Frameworks`, não ao lado do executável |
| `core/config.py` | Configuração em `~/Library/Application Support/anonimizador_dpu/` | Local convencional do macOS (no Windows continua `%APPDATA%`) |
| `app/main.py` | Estilo **Fusion** no Mac | A folha de estilo do aplicativo desfigura abas e botões no estilo nativo do macOS; o Fusion a respeita, acompanha o tema claro/escuro e deixa a janela igual à do Windows |
| `app/main.py` | Carrega a tradução do Qt para português (todas as plataformas; sem efeito no executável Windows, que não leva o arquivo) | Botões "Sim/Não" em vez de "Yes/No" e menu do aplicativo em português |
| `app/ui/main_window.py` | "Sair" e "Sobre" vão para o menu do aplicativo (Cmd+Q); demais itens ficam onde estão | Padrão do Mac |
| `app/ui/main_window.py` | Janela inicial de 1440 × 820 pontos, nunca maior que a área útil da tela; área da página com altura mínima de 420 (era 560) | A fonte do sistema no Mac é maior: com os valores originais, a janela exigia no mínimo 1735 × 886 e não cabia na tela de um MacBook Air; a página também cobria a legenda abaixo dela |
| `app/ui/review_panel.py` | Botões de "Decisões" em duas fileiras de três; campo de busca com largura mínima | Mesmo motivo: numa fileira só, os botões impunham a largura de 1735 pontos, e o campo de busca ficava espremido |

### Fora do aplicativo

* `tests/fixtures/gerador.py` — acrescenta a fonte Arial do macOS. Sem ela, as
  imagens "digitalizadas" dos testes saíam com a fonte minúscula embutida do
  Pillow e os testes de OCR falhavam.
* `scripts/mac/` — tudo o que gera a versão para Mac (abaixo).

## Como gerar

A partir da raiz do projeto, num Mac com chip Apple:

```bash
scripts/mac/instalar.sh          # Python portátil + .venv + dependências (uma vez)
scripts/mac/construir_tesseract.sh   # compila o OCR embutido (uma vez, ~30 s)
scripts/mac/testar.sh            # suíte de testes
scripts/mac/gerar_pacote.sh      # testes + .app + DMG/ZIP, com conferência
```

| Script | Equivale a | Função |
|---|---|---|
| `instalar.sh` | `instalar.bat` | Baixa o Python 3.13 portátil (conferido por SHA-256), cria o `.venv`, instala `requirements-mac.txt` |
| `executar.sh` | `executar.bat` | Abre o aplicativo a partir do código |
| `testar.sh` | `testar.bat` | Roda a suíte (janelas de teste fora da tela) |
| `construir_tesseract.sh` | — | Compila libpng, libjpeg-turbo, libtiff, Leptonica e Tesseract, todos estáticos, em um único executável que só depende do próprio macOS; baixa os idiomas; tudo conferido por SHA-256 |
| `gerar_app.sh` | `gerar_executavel.bat` | Testes, ícone, PyInstaller (`anonimizador_dpu_mac.spec`), conferência da assinatura e `--verificar` no aplicativo pronto |
| `montar_pacote_mac.sh` | `montar_pacote.py` | Monta `dist/AnonimizadorDPU-mac.dmg` e `.zip` com aplicativo, documentação, código-fonte, `INSTALAR.txt` e `LICENCAS.txt`; monta o DMG e confere o aplicativo de dentro dele |
| `gerar_pacote.sh` | `gerar_pacote.bat` | `gerar_app.sh` + `montar_pacote_mac.sh` |

Resultado medido em macOS 27.2 (MacBook Air M5): **324 testes aprovados**, o
mesmo número da versão Windows, incluindo os de OCR; aplicativo de 186 MB.

## Decisões de compatibilidade (e o que foi descartado)

* **Python portátil, e não o do Homebrew.** O PyInstaller copia a biblioteca do
  Python para dentro do aplicativo. A do Homebrew é compilada para o macOS da
  máquina (macOS 26 ou mais novo), e o aplicativo deixaria de abrir em sistemas
  anteriores. O python-build-standalone aceita macOS 11+.
* **PySide6 6.11.3, e não 6.12.0.** Os binários do PySide6 6.12.0 para Mac
  foram compilados para macOS 26, embora o pacote se anuncie como macOS 14. A
  6.11.3 aceita macOS 15 e expõe a mesma interface usada pelo aplicativo. É ela
  que define o mínimo de macOS 15.
* **Tesseract compilado, e não copiado do Homebrew.** Mesmo motivo do Python,
  e o do Homebrew depende de uma dúzia de bibliotecas em `/opt/homebrew`. O
  compilado é um executável único, sem libcurl (não lê endereços da internet),
  aceito desde o macOS 12.
* **libtiff e libjpeg-turbo no Tesseract.** Sem elas, a Leptonica não consegue
  ler a própria fonte interna e o Tesseract imprime "Error in bmfCreate" a cada
  execução; o pytesseract lê essas linhas como se fossem idiomas instalados.
* **Estilo nativo do macOS: descartado.** Com a folha de estilo do aplicativo,
  as abas ficam com divisórias tortas e os botões perdem o contorno.
* **Diminuir a fonte: descartado.** O macOS fixa a fonte de botões e caixas; a
  largura mínima da janela não muda.
* **Versão universal (Intel + Apple): não feita.** O PyMuPDF não publica
  pacote universal, e não havia Mac Intel (nem Rosetta) para testar.

## Limitações próprias da versão Mac

* Sem assinatura Developer ID nem notarização: a primeira abertura exige a
  liberação manual descrita acima. Assinar e notarizar exige conta paga no
  Apple Developer Program.
* Só Apple Silicon e macOS 15+.
* As limitações gerais da ferramenta (`docs/LIMITACOES.md`) valem igualmente.
