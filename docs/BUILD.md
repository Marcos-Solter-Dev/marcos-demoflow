# Build para macOS e Windows

O projeto usa PyInstaller para gerar aplicativos desktop.

## macOS — `.app`

No Mac:

```bash
chmod +x build_macos.command
./build_macos.command
```

O script valida Python/Tk, cria uma `.venv-build`, instala dependências, gera o `.icns` e cria:

```text
dist/Marcos DemoFlow.app
```

Para abrir:

```bash
open "dist/Marcos DemoFlow.app"
```

Para ver erros do executável empacotado:

```bash
./run_built_macos_debug.command
```

### Gatekeeper

O build local não é assinado nem notarizado. Para distribuição pública sem alertas, é necessário assinar e notarizar o aplicativo com uma conta Apple Developer.

## Windows — `.exe`

No Windows:

```text
build_windows.bat
```

Resultado:

```text
dist\Marcos DemoFlow.exe
```

O executável local não possui assinatura Authenticode; por isso, o SmartScreen pode exibir um aviso.

## Gerar os dois sistemas a partir do Mac

O PyInstaller não faz cross-compile de Windows a partir do macOS. O workflow `.github/workflows/build-desktop.yml` usa runners separados.

Com GitHub CLI:

```bash
brew install gh
gh auth login
chmod +x build_all_from_mac.command
./build_all_from_mac.command
```

Os artefatos são baixados para `dist/github/`.
