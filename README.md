<p align="center">
  <img src="assets/app_icon.png" width="108" alt="Marcos DemoFlow">
</p>

<h1 align="center">Marcos DemoFlow</h1>

<p align="center">
  Gravador de demonstrações para macOS e Windows com timeline, automação de navegador e movimentos cinematográficos.
</p>

<p align="center">
  <a href="https://github.com/Marcos-Solter-Dev/marcos-demoflow/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/Marcos-Solter-Dev/marcos-demoflow/actions/workflows/ci.yml/badge.svg"></a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Platforms" src="https://img.shields.io/badge/Platforms-macOS%20%7C%20Windows-016FF7">
  <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/License-Marcos%20Dev%20Source--Available-016FF7.svg"></a>
</p>

## Visão geral

O **Marcos DemoFlow** grava demonstrações de sites e interfaces sem alterar o HTML, CSS ou JavaScript da página. Você monta um roteiro visual, escolhe uma janela ou aba do Chrome e o aplicativo executa o fluxo enquanto grava o resultado em vídeo.

O projeto nasceu para produzir demos mais consistentes do que uma gravação manual: movimentos de cursor suavizados, scroll contínuo, foco de câmera, cliques, pausas, digitação e tours automáticos podem ser organizados em uma timeline antes da gravação.

## Recursos principais

- timeline editável com reordenação, duplicação e edição de ações;
- clique, movimento do cursor, foco/zoom, pausa, digitação e atalhos;
- scroll cinematográfico e scroll contínuo de página inteira;
- posição de ações vinculada ao documento, não apenas à coordenada da tela;
- scroll automático antes de ações localizadas fora da viewport;
- análise da aba do Chrome para gerar tours automaticamente;
- recarregamento opcional com `⌘R`/`Ctrl+R` para registrar animações de entrada;
- modo de tela cheia antes da gravação;
- temas Claro e Escuro no estilo Marcos Dev;
- exportação MP4 com presets de resolução e FPS;
- projetos salvos em JSON;
- build local para `.app` no macOS e `.exe` no Windows;
- workflow do GitHub Actions para gerar builds dos dois sistemas.

## Requisitos

### macOS

- macOS com Python 3.11 ou superior;
- Tk 8.6 ou superior;
- Google Chrome para recursos de análise de aba/DOM;
- permissões de **Acessibilidade**, **Gravação da Tela** e **Automação** quando solicitadas.

Para evitar problemas de Tk no macOS, o caminho recomendado é Python 3.12 + Tk 8.6/8.7.

### Windows

- Windows 10/11;
- Python 3.11 ou superior com Tcl/Tk;
- Google Chrome para os recursos de automação de aba.

## Instalação rápida

### macOS

```bash
chmod +x setup_macos.sh run_macos.sh
./setup_macos.sh
./run_macos.sh
```

### Windows

Execute:

```text
setup_windows.bat
run_windows.bat
```

A instalação detalhada, incluindo permissões do macOS e configuração do Chrome, está em [`docs/INSTALLATION.md`](docs/INSTALLATION.md).

## Uso básico

1. Abra o Chrome e deixe a página que deseja demonstrar disponível.
2. No DemoFlow, atualize a lista de janelas/abas e escolha a aba correta.
3. Adicione ações manualmente ou gere um tour automático.
4. Revise a timeline.
5. Configure saída, resolução, FPS e preparação da gravação.
6. Clique em **Iniciar gravação**.
7. Pressione `F8` para interromper a execução a qualquer momento.

Para ações posicionadas mais abaixo na página, o DemoFlow salva a posição dentro do documento e cria o scroll necessário antes da ação. Se o alvo não puder ser localizado com segurança, a ação é ignorada em vez de clicar em uma coordenada antiga.

## Gerar `.app` e `.exe`

### macOS — gerar `.app`

```bash
chmod +x build_macos.command
./build_macos.command
```

Resultado:

```text
dist/Marcos DemoFlow.app
```

### Windows — gerar `.exe`

No Windows:

```text
build_windows.bat
```

Resultado:

```text
dist\Marcos DemoFlow.exe
```

### Gerar Windows e macOS a partir do Mac

O PyInstaller não faz cross-compile de Windows a partir do macOS. Para gerar os dois sistemas a partir de um Mac, o repositório inclui um workflow do GitHub Actions e o script:

```bash
./build_all_from_mac.command
```

Ele usa a GitHub CLI (`gh`) para iniciar o workflow em runners Windows e macOS e baixar os artefatos ao final. Veja [`docs/BUILD.md`](docs/BUILD.md).

## Estrutura

```text
marcos-demoflow/
├── app.py
├── demoflow/
│   ├── chrome_tabs.py
│   ├── dom_inspector.py
│   ├── easing.py
│   ├── engine.py
│   ├── models.py
│   ├── recorder.py
│   ├── tour_builder.py
│   └── windowing.py
├── assets/
├── docs/
├── examples/
├── scripts/
├── .github/workflows/
├── build_macos.command
├── build_windows.bat
├── setup_macos.sh
├── setup_windows.bat
├── run_macos.sh
├── run_windows.bat
└── requirements.txt
```

A divisão de responsabilidades está documentada em [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Problemas comuns

Os casos mais frequentes estão documentados em [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md), incluindo:

- janela preta ou widgets invisíveis no macOS;
- permissões de gravação de tela e acessibilidade;
- Chrome não aparecendo na lista de abas;
- clique ocorrendo no lugar errado;
- scroll que não chega ao rodapé;
- build `.app` bloqueado pelo Gatekeeper;
- SmartScreen no Windows;
- falhas ao gerar `.app` ou `.exe`.

## Verificação do projeto

Antes de publicar uma mudança:

```bash
python scripts/verify.py
```

O script valida sintaxe Python, estrutura mínima do projeto, arquivos de build e assets obrigatórios.

## Segurança e privacidade

O DemoFlow controla mouse/teclado e captura a tela durante a gravação. Use somente em páginas, contas e ambientes em que você tenha autorização. Revise a tela antes de gravar para não expor senhas, tokens, e-mails ou dados pessoais.

Veja [`SECURITY.md`](SECURITY.md).

## Contribuindo

Issues para bugs e sugestões são bem-vindas. Antes de enviar alterações, leia [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Licença

**Marcos Dev Source-Available License v1.0.** O uso, estudo e modificação para uso próprio são permitidos, mas a redistribuição ou republicação do projeto não é permitida sem autorização da Marcos Dev. Veja [`LICENSE`](LICENSE) e [`MARCOSDEV.md`](MARCOSDEV.md).
