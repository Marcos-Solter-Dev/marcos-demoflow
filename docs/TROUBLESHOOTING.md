# Problemas e soluções

## A janela abre preta ou quase vazia no macOS

**Causa comum:** Python/Tk antigo ou ambiente virtual criado com Tk incompatível.

```bash
brew install python@3.12 python-tk@3.12
rm -rf .venv .venv-build
./setup_macos.sh
./run_macos.sh
```

Para o `.app`, refaça com `./build_macos.command`; o script atual valida Tk 8.6+.

## `DEPRECATION WARNING: The system version of Tk is deprecated`

Use uma instalação atual de Python/Tk e recrie o ambiente virtual. Não esconda apenas o aviso.

## A gravação fica preta

Confirme a permissão de **Gravação da Tela** para Terminal, Python ou `Marcos DemoFlow.app`. Feche e reabra o processo após alterar a permissão.

## Mouse/teclado não funcionam no macOS

Ative **Acessibilidade** para o processo que executa o DemoFlow.

## A aba do Chrome não aparece

- confirme que o Chrome está aberto;
- clique em **Atualizar abas**;
- escolha uma aba específica;
- confira a permissão de Automação;
- habilite JavaScript de eventos da Apple no Chrome para análise DOM.

## O clique ocorre no lugar errado

Projetos antigos podem conter apenas coordenadas de tela. Recapture a ação na versão atual escolhendo uma aba específica do Chrome. Use **Corrigir scrolls dos alvos** quando necessário.

## O DemoFlow clica no vazio

Ações page-aware são revalidadas antes do clique. Se o elemento não puder ser localizado depois do scroll, a ação é ignorada.

## O scroll contínuo dá um salto no final

O motor atual usa velocidade em px/s e recalcula a altura da página. Em sites de carregamento infinito, prefira tour por alvos ou ações manuais.

## O `.app` não abre pelo Finder

```bash
./run_built_macos_debug.command
```

Se o Gatekeeper bloquear um build local, autorize em **Privacidade e Segurança** ou assine/notarize o app.

## Windows mostra SmartScreen

Builds locais não são assinados. Para distribuição pública profissional, assine o executável com certificado de code signing.

## `ModuleNotFoundError`

Ative a `.venv` correta e reinstale:

```bash
pip install -r requirements.txt
```

## O MP4 não é criado ou fica vazio

Confira a pasta de saída, espaço em disco, resolução e se a gravação iniciou antes de ser interrompida.
