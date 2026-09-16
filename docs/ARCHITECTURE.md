# Arquitetura

O Marcos DemoFlow é dividido em módulos pequenos.

## `app.py`

Interface Tkinter, timeline, configuração de gravação, seleção de janelas/abas, temas e orquestração.

## `demoflow/models.py`

Modelos de projeto, ações, serialização JSON e configurações de gravação.

## `demoflow/windowing.py`

Descoberta de janelas e geometria usada na captura.

## `demoflow/chrome_tabs.py`

Lista e ativa abas do Google Chrome. No macOS usa AppleScript/Apple Events.

## `demoflow/dom_inspector.py`

Lê elementos da página, resolve coordenadas no documento e calcula scroll alvo.

## `demoflow/engine.py`

Executa ações da timeline e implementa proteções para não clicar em alvos inválidos.

## `demoflow/recorder.py`

Captura frames com `mss`, aplica cursor/efeitos e grava MP4 com OpenCV.

## `demoflow/tour_builder.py`

Transforma a análise da página em tours automáticos.

## `demoflow/easing.py`

Curvas de aceleração usadas nos movimentos.

## Limites

Layouts que mudam continuamente, iframes de terceiros e páginas de carregamento infinito podem exigir ajustes manuais na timeline.
