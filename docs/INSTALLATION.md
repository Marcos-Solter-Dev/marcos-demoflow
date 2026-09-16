# Instalação

## macOS

### Recomendado

Use Python 3.12 com Tk 8.6 ou superior. Com Homebrew:

```bash
brew install python@3.12 python-tk@3.12
```

Depois:

```bash
chmod +x setup_macos.sh run_macos.sh
./setup_macos.sh
./run_macos.sh
```

O script cria uma `.venv` local e instala as dependências do projeto.

### Permissões

Na primeira execução, o macOS pode pedir acesso a:

- **Acessibilidade** — necessário para mouse e teclado;
- **Gravação da Tela** — necessário para capturar a janela;
- **Automação** — necessário quando o DemoFlow controla o Google Chrome.

Se uma permissão tiver sido negada, abra **Ajustes do Sistema → Privacidade e Segurança** e revise a categoria correspondente.

### Chrome e análise de elementos

Recursos que identificam elementos reais da página usam JavaScript executado na aba do Chrome por Apple Events. Quando necessário, habilite no Chrome a opção de permitir JavaScript de eventos da Apple no menu de desenvolvimento.

Sem essa permissão, a gravação de janela continua disponível, mas ações page-aware e tours automáticos podem não conseguir ler o DOM.

## Windows

Instale Python 3.11 ou superior pelo site oficial e marque a opção para adicionar Python ao `PATH`.

Depois execute:

```text
setup_windows.bat
run_windows.bat
```

O projeto cria uma `.venv` local e instala as dependências, incluindo `PyGetWindow` no Windows.

## Executar manualmente

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Windows:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
