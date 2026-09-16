from __future__ import annotations
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import platform
import sys
import pyautogui

from demoflow import __version__
from demoflow.models import WindowInfo, Action, RecordingConfig, save_project, load_project
from demoflow.windowing import list_windows
from demoflow.chrome_tabs import ChromeTab, list_chrome_tabs, activate_chrome_tab, get_active_chrome_tab
from demoflow.recorder import ScreenRecorder
from demoflow.engine import DemoEngine
from demoflow.dom_inspector import inspect_chrome_site, capture_site_point, scroll_page_to, get_page_scroll_state
from demoflow.tour_builder import TourOptions, build_tour_actions, FullPageScrollOptions, build_full_page_scroll_tour

APP_NAME = f"Marcos DemoFlow V{__version__}"


class App(tk.Tk):
    def __init__(self):
        super().__init__()

        if platform.system() == "Darwin":
            print(f"[DemoFlow] Python: {platform.python_version()} | Tk: {tk.TkVersion} | Tcl: {tk.TclVersion}")
            if tk.TkVersion < 8.6:
                print("[DemoFlow] AVISO: Tk antigo detectado. Use Python 3.12 + Tk 8.6/8.7 para evitar janela preta.")

        self.title(APP_NAME)
        self._apply_app_icon()
        self.geometry("1260x820")
        self.minsize(1080, 680)

        self.windows: list[WindowInfo] = []
        self.chrome_tabs: list[ChromeTab] = []
        self.actions: list[Action] = []
        self.engine: DemoEngine | None = None
        self.recorder: ScreenRecorder | None = None
        self.worker: threading.Thread | None = None

        self.window_var = tk.StringVar()
        self.chrome_tab_var = tk.StringVar(value="— Usar aba atualmente ativa —")
        self.browser_only_var = tk.BooleanVar(value=True)
        self.output_var = tk.StringVar(value=str(Path.home() / "Desktop" / "demo-profissional-v2.18.mp4"))
        self.fps_var = tk.IntVar(value=30)
        self.resolution_var = tk.StringVar(value="Nativa")
        self.cursor_var = tk.StringVar(value="ring")
        self.transition_var = tk.StringVar(value="zoom")
        self.show_clicks_var = tk.BooleanVar(value=True)
        self.countdown_var = tk.IntVar(value=3)

        # V2.10 — checklist de preparação da gravação.
        self.fullscreen_before_record_var = tk.BooleanVar(value=False)
        self.intro_animation_var = tk.BooleanVar(value=False)
        self.intro_animation_wait_var = tk.DoubleVar(value=2.5)
        self.status_var = tk.StringVar(value="Pronto.")
        self.capture_countdown_var = tk.StringVar(value="")
        self.duration_var = tk.StringVar(value="0 ações · 0,0 s")

        # V2.13 — tema próprio Marcos Dev. Claro é o padrão,
        # independentemente do modo de aparência do macOS.
        self.theme_var = tk.StringVar(value="Claro")
        self._palette: dict[str, str] = {}

        self._build_style()
        self._build_ui()
        self.apply_theme(self.theme_var.get())
        self.after(60, self._verify_ttk_theme)

        # V2.8: rolagem da coluna "Adicionar ações".
        # O handler é global, mas só age quando o ponteiro está sobre a coluna.
        self.bind_all("<MouseWheel>", self._on_tools_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_tools_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_tools_mousewheel, add="+")
        self.bind_all("<MouseWheel>", self._on_capture_mousewheel, add="+")
        self.bind_all("<Button-4>", self._on_capture_mousewheel, add="+")
        self.bind_all("<Button-5>", self._on_capture_mousewheel, add="+")

        self.bind("<F8>", lambda _e: self.stop_run())
        self.bind("<Command-Return>", lambda _e: self.start_run(record=True))
        self.bind("<Control-Return>", lambda _e: self.start_run(record=True))
        self.after(120, self.refresh_all_sources)



    @staticmethod
    def _resource_path(relative: str) -> Path:
        """Retorna um recurso tanto em desenvolvimento quanto em builds PyInstaller."""
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        return base / relative

    def _apply_app_icon(self):
        """Carrega o ícone do app em desenvolvimento e em builds empacotados."""
        try:
            png_path = self._resource_path("assets/app_icon.png")
            ico_path = self._resource_path("assets/app_icon.ico")

            self._app_icon_image = None

            if png_path.exists():
                self._app_icon_image = tk.PhotoImage(file=str(png_path))
                try:
                    self.iconphoto(True, self._app_icon_image)
                except tk.TclError:
                    pass

            if platform.system() == "Windows" and ico_path.exists():
                try:
                    self.iconbitmap(default=str(ico_path))
                except tk.TclError:
                    pass
        except Exception:
            self._app_icon_image = None

    @staticmethod
    def _theme_palette(mode: str) -> dict[str, str]:
        if str(mode).lower().startswith("esc"):
            return {
                "bg": "#0B111A",
                "surface": "#111A27",
                "surface_alt": "#162233",
                "text": "#F4F7FB",
                "muted": "#9AA8BC",
                "line": "#29384D",
                "accent": "#016FF7",
                "accent_hover": "#58A4EC",
                "button_bg": "#1B293B",
                "button_hover": "#24364D",
                "button_fg": "#F4F7FB",
                "input_bg": "#0E1723",
                "input_fg": "#F4F7FB",
                "tree_bg": "#0E1723",
                "tree_fg": "#EDF3FA",
                "tree_head": "#162233",
                "select_bg": "#173D69",
                "select_fg": "#FFFFFF",
                "status_bg": "#06152D",
                "status_fg": "#FFFFFF",
                "status_muted": "#B8C6D9",
            }

        return {
            "bg": "#FEFEFE",
            "surface": "#FFFFFF",
            "surface_alt": "#F6F8FB",
            "text": "#0B1730",
            "muted": "#68758A",
            "line": "#DCE4EF",
            "accent": "#016FF7",
            "accent_hover": "#005FCC",
            "button_bg": "#F1F5FA",
            "button_hover": "#E7EEF7",
            "button_fg": "#0B1730",
            "input_bg": "#FFFFFF",
            "input_fg": "#0B1730",
            "tree_bg": "#FFFFFF",
            "tree_fg": "#0B1730",
            "tree_head": "#F6F8FB",
            "select_bg": "#DCEEFF",
            "select_fg": "#0B1730",
            "status_bg": "#06152D",
            "status_fg": "#FFFFFF",
            "status_muted": "#C8D3E2",
        }

    def _build_style(self):
        style = ttk.Style(self)

        # Nunca usamos Aqua como base para a interface customizada.
        # Em alguns builds empacotados do macOS, Aqua + aparência escura pode
        # deixar labels/botões praticamente invisíveis.
        self._ttk_base_theme = "default"
        try:
            available = tuple(style.theme_names())
            for candidate in ("clam", "alt", "classic", "default"):
                if candidate in available:
                    style.theme_use(candidate)
                    self._ttk_base_theme = candidate
                    break
        except tk.TclError:
            self._ttk_base_theme = "default"

        # As cores são aplicadas em apply_theme(), depois que os widgets existem.
        style.configure("HeaderTitle.TLabel", font=("TkDefaultFont", 20, "bold"))
        style.configure("HeaderSub.TLabel", font=("TkDefaultFont", 10))
        style.configure("Section.TLabel", font=("TkDefaultFont", 9, "bold"))
        style.configure("CardTitle.TLabel", font=("TkDefaultFont", 10, "bold"))
        style.configure("Muted.TLabel", font=("TkDefaultFont", 9))
        style.configure("SidebarNote.TLabel", font=("TkDefaultFont", 9))
        style.configure("TimelineTitle.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Small.TButton", padding=(8, 4))
        style.configure("Treeview", rowheight=30)
        style.configure("Treeview.Heading", font=("TkDefaultFont", 9, "bold"))

    def apply_theme(self, mode: str | None = None):
        mode = mode or self.theme_var.get() or "Claro"
        if mode not in {"Claro", "Escuro"}:
            mode = "Claro"
        self.theme_var.set(mode)

        p = self._theme_palette(mode)
        self._palette = p
        style = ttk.Style(self)

        # Reforça o tema não-nativo inclusive dentro do .app empacotado.
        try:
            base_theme = getattr(self, "_ttk_base_theme", "clam")
            if base_theme in style.theme_names():
                style.theme_use(base_theme)
        except tk.TclError:
            pass

        self.configure(bg=p["bg"])

        # Também força a paleta Tk clássica. Isso dá um fallback visual caso
        # algum widget não respeite uma configuração ttk específica.
        try:
            self.tk_setPalette(
                background=p["bg"],
                foreground=p["text"],
                activeBackground=p["button_hover"],
                activeForeground=p["text"],
                highlightColor=p["accent"],
                selectBackground=p["select_bg"],
                selectForeground=p["select_fg"],
            )
        except tk.TclError:
            pass

        style.configure("TFrame", background=p["bg"])
        style.configure("App.TFrame", background=p["bg"])
        style.configure("Surface.TFrame", background=p["surface"])
        style.configure("TLabel", background=p["bg"], foreground=p["text"])
        style.configure("HeaderTitle.TLabel", background=p["bg"], foreground=p["text"])
        style.configure("HeaderSub.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure("Section.TLabel", background=p["bg"], foreground=p["accent"])
        style.configure("CardTitle.TLabel", background=p["bg"], foreground=p["text"])
        style.configure("Muted.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure("SidebarNote.TLabel", background=p["bg"], foreground=p["muted"])
        style.configure("TimelineTitle.TLabel", background=p["bg"], foreground=p["text"])

        style.configure(
            "TLabelframe",
            background=p["bg"],
            foreground=p["text"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.configure(
            "TLabelframe.Label",
            background=p["bg"],
            foreground=p["text"],
            font=("TkDefaultFont", 9, "bold"),
        )

        style.configure(
            "TButton",
            background=p["button_bg"],
            foreground=p["button_fg"],
            bordercolor=p["line"],
            lightcolor=p["button_bg"],
            darkcolor=p["button_bg"],
            focusthickness=0,
            padding=(9, 5),
        )
        style.map(
            "TButton",
            background=[
                ("pressed", p["button_hover"]),
                ("active", p["button_hover"]),
            ],
            foreground=[
                ("disabled", p["muted"]),
                ("active", p["button_fg"]),
                ("pressed", p["button_fg"]),
            ],
        )
        style.configure(
            "Small.TButton",
            background=p["button_bg"],
            foreground=p["button_fg"],
            bordercolor=p["line"],
            padding=(8, 4),
        )
        style.map(
            "Small.TButton",
            background=[("active", p["button_hover"]), ("pressed", p["button_hover"])],
            foreground=[("active", p["button_fg"]), ("pressed", p["button_fg"])],
        )

        style.configure(
            "TCheckbutton",
            background=p["bg"],
            foreground=p["text"],
        )
        style.map(
            "TCheckbutton",
            background=[("active", p["bg"])],
            foreground=[("disabled", p["muted"]), ("active", p["text"])],
        )

        style.configure(
            "TEntry",
            fieldbackground=p["input_bg"],
            foreground=p["input_fg"],
            insertcolor=p["input_fg"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=p["input_bg"],
            foreground=p["input_fg"],
            insertcolor=p["input_fg"],
            arrowsize=12,
            bordercolor=p["line"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=p["input_bg"],
            background=p["button_bg"],
            foreground=p["input_fg"],
            arrowcolor=p["muted"],
            bordercolor=p["line"],
            lightcolor=p["line"],
            darkcolor=p["line"],
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p["input_bg"])],
            foreground=[("readonly", p["input_fg"])],
            selectbackground=[("readonly", p["input_bg"])],
            selectforeground=[("readonly", p["input_fg"])],
        )

        style.configure(
            "Treeview",
            background=p["tree_bg"],
            fieldbackground=p["tree_bg"],
            foreground=p["tree_fg"],
            bordercolor=p["line"],
            rowheight=30,
        )
        style.map(
            "Treeview",
            background=[("selected", p["select_bg"])],
            foreground=[("selected", p["select_fg"])],
        )
        style.configure(
            "Treeview.Heading",
            background=p["tree_head"],
            foreground=p["text"],
            bordercolor=p["line"],
            font=("TkDefaultFont", 9, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", p["button_hover"])],
            foreground=[("active", p["text"])],
        )

        style.configure("TSeparator", background=p["line"])
        style.configure(
            "Vertical.TScrollbar",
            background=p["button_bg"],
            troughcolor=p["surface_alt"],
            bordercolor=p["line"],
            arrowcolor=p["muted"],
        )
        style.configure("TPanedwindow", background=p["line"])

        # Widgets tk que não obedecem ttk.Style.
        if hasattr(self, "record_button"):
            self.record_button.configure(
                bg=p["accent"],
                fg="#FFFFFF",
                activebackground=p["accent_hover"],
                activeforeground="#FFFFFF",
                highlightthickness=0,
            )

        if hasattr(self, "tools_canvas"):
            self.tools_canvas.configure(
                background=p["bg"],
                highlightbackground=p["line"],
            )

        if hasattr(self, "capture_canvas"):
            self.capture_canvas.configure(
                background=p["bg"],
                highlightbackground=p["line"],
            )

        if hasattr(self, "status_frame"):
            self.status_frame.configure(
                bg=p["status_bg"],
                highlightbackground=p["line"],
            )
        if hasattr(self, "status_label"):
            self.status_label.configure(bg=p["status_bg"], fg=p["status_fg"])
        if hasattr(self, "status_help_label"):
            self.status_help_label.configure(bg=p["status_bg"], fg=p["status_muted"])

        # Combobox popup no Tk/clam, quando disponível.
        try:
            self.option_add("*TCombobox*Listbox.background", p["input_bg"])
            self.option_add("*TCombobox*Listbox.foreground", p["input_fg"])
            self.option_add("*TCombobox*Listbox.selectBackground", p["select_bg"])
            self.option_add("*TCombobox*Listbox.selectForeground", p["select_fg"])
        except tk.TclError:
            pass

    def _verify_ttk_theme(self):
        """Reaplica o tema caso o macOS/PyInstaller tenha mudado o ttk após o startup."""
        try:
            style = ttk.Style(self)
            current = style.theme_use()
            preferred = getattr(self, "_ttk_base_theme", "clam")
            if current in {"aqua"} and preferred in style.theme_names():
                style.theme_use(preferred)
                self.apply_theme(self.theme_var.get())
        except tk.TclError:
            pass

    def _on_theme_selected(self, _event=None):
        self.apply_theme(self.theme_var.get())

    def _build_ui(self):
        outer = ttk.Frame(self, padding=16, style="App.TFrame")
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer, style="App.TFrame")
        header.pack(fill="x")

        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text=APP_NAME, style="HeaderTitle.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Crie demonstrações profissionais automaticamente.",
            style="HeaderSub.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        quick_meta = ttk.Frame(header, style="App.TFrame")
        quick_meta.pack(side="right", anchor="n")
        theme_row = ttk.Frame(quick_meta, style="App.TFrame")
        theme_row.pack(anchor="e", pady=(0, 5))
        ttk.Label(theme_row, text="Tema", style="Muted.TLabel").pack(side="left", padx=(0, 6))
        self.theme_combo = ttk.Combobox(
            theme_row,
            state="readonly",
            width=9,
            textvariable=self.theme_var,
            values=("Claro", "Escuro"),
        )
        self.theme_combo.pack(side="left")
        self.theme_combo.bind("<<ComboboxSelected>>", self._on_theme_selected)

        ttk.Label(quick_meta, text="⌘↩ Gravar", style="Muted.TLabel").pack(anchor="e", pady=(3, 0))
        ttk.Label(quick_meta, text="F8 parar", style="Muted.TLabel").pack(anchor="e", pady=(2, 0))

        ttk.Separator(outer).pack(fill="x", pady=(12, 12))

        actionbar = ttk.Frame(outer, style="App.TFrame")
        actionbar.pack(fill="x", pady=(0, 12))

        self.record_button = tk.Button(
            actionbar,
            text="Iniciar gravação",
            command=lambda: self.start_run(record=True),
            bg="#016FF7", fg="#ffffff",
            activebackground="#005FCC", activeforeground="#ffffff",
            font=("TkDefaultFont", 11, "bold"),
            relief="flat", bd=0, padx=18, pady=7, cursor="hand2",
        )
        self.record_button.pack(side="left")
        ttk.Button(actionbar, text="Testar", command=lambda: self.start_run(record=False), style="Small.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(actionbar, text="Parar", command=self.stop_run, style="Small.TButton").pack(side="left", padx=(8, 0))
        ttk.Label(actionbar, textvariable=self.duration_var, style="Muted.TLabel").pack(side="right", pady=(6, 0))

        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        # Sidebar com categorias de ação
        tools_host = ttk.LabelFrame(body, text="Adicionar ação", padding=0)
        body.add(tools_host, weight=0)

        tools_canvas_bg = "#fefefe"
        self.tools_canvas = tk.Canvas(
            tools_host,
            width=285,
            highlightthickness=0,
            borderwidth=0,
            background=tools_canvas_bg,
        )
        self.tools_scrollbar = ttk.Scrollbar(
            tools_host,
            orient="vertical",
            command=self.tools_canvas.yview,
        )
        self.tools_canvas.configure(yscrollcommand=self.tools_scrollbar.set)

        self.tools_scrollbar.pack(side="right", fill="y")
        self.tools_canvas.pack(side="left", fill="both", expand=True)

        tools = ttk.Frame(self.tools_canvas, padding=(12, 10, 10, 12), style="App.TFrame")
        self.tools_inner = tools
        self._tools_window_id = self.tools_canvas.create_window((0, 0), window=tools, anchor="nw")

        def _sync_tools_scrollregion(_event=None):
            self.tools_canvas.configure(scrollregion=self.tools_canvas.bbox("all"))

        def _fit_tools_width(event):
            self.tools_canvas.itemconfigure(self._tools_window_id, width=max(1, event.width))
            _sync_tools_scrollregion()

        tools.bind("<Configure>", _sync_tools_scrollregion)
        self.tools_canvas.bind("<Configure>", _fit_tools_width)

        ttk.Label(tools, text="Ações organizadas por categoria.", style="Muted.TLabel").pack(anchor="w", pady=(0, 8))

        def section(title: str):
            ttk.Label(tools, text=title.upper(), style="Section.TLabel").pack(anchor="w", pady=(10, 4))

        def action_button(label: str, command):
            ttk.Button(tools, text=label, command=command).pack(fill="x", pady=3)

        section("Interação")
        action_button("◉ Clique", self.capture_click)
        action_button("⊙ Clique inteligente", self.capture_smart_click)
        action_button("↗ Mover cursor", self.capture_move)
        action_button("◎ Foco / zoom", self.capture_focus)

        section("Movimento")
        action_button("↓ Scroll para baixo", lambda: self.add_scroll(-8))
        action_button("↑ Scroll para cima", lambda: self.add_scroll(8))
        action_button("⏱ Pausa", self.add_wait)

        section("Página")
        action_button("⌨ Digitar texto", self.add_type)
        action_button("⌘ Atalho de teclado", self.add_hotkey)
        action_button("↻ Corrigir scrolls dos alvos", self.repair_target_scrolls)

        section("Automação")
        self.auto_tour_button = ttk.Button(tools, text="✦ Tour automático", command=self.generate_automatic_tour)
        self.auto_tour_button.pack(fill="x", pady=3)
        self.full_page_tour_button = ttk.Button(tools, text="▣ Página inteira", command=self.generate_full_page_scroll_tour)
        self.full_page_tour_button.pack(fill="x", pady=3)
        self.continuous_scroll_button = ttk.Button(tools, text="≋ Scroll contínuo", command=self.generate_continuous_full_page_scroll)
        self.continuous_scroll_button.pack(fill="x", pady=3)
        action_button("→ Tour simples", self.generate_scroll_tour)

        ttk.Separator(tools).pack(fill="x", pady=10)
        ttk.Label(
            tools,
            text="Alvos fora da tela recebem scroll automático. Se um alvo não for localizado, a ação é ignorada.",
            justify="left",
            wraplength=240,
            style="SidebarNote.TLabel",
        ).pack(anchor="w")
        ttk.Label(tools, textvariable=self.capture_countdown_var, style="CardTitle.TLabel").pack(anchor="w", pady=(8, 0))

        # Timeline
        center = ttk.Frame(body, style="App.TFrame")
        body.add(center, weight=1)

        timeline_header = ttk.Frame(center, style="App.TFrame")
        timeline_header.pack(fill="x", pady=(0, 8))
        ttk.Label(timeline_header, text="Timeline", style="TimelineTitle.TLabel").pack(side="left")
        ttk.Label(timeline_header, text="Roteiro das ações que serão gravadas.", style="Muted.TLabel").pack(side="left", padx=(10, 0))

        toolbar = ttk.Frame(center, style="App.TFrame")
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="↑", width=4, command=lambda: self.move_action(-1), style="Small.TButton").pack(side="left")
        ttk.Button(toolbar, text="↓", width=4, command=lambda: self.move_action(1), style="Small.TButton").pack(side="left", padx=(4, 0))
        ttk.Button(toolbar, text="Editar", command=self.edit_action, style="Small.TButton").pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Duplicar", command=self.duplicate_action, style="Small.TButton").pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Excluir", command=self.delete_action, style="Small.TButton").pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Limpar", command=self.clear_actions, style="Small.TButton").pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Abrir projeto", command=self.load_script, style="Small.TButton").pack(side="right")
        ttk.Button(toolbar, text="Salvar projeto", command=self.save_script, style="Small.TButton").pack(side="right", padx=(0, 6))

        table_wrap = ttk.LabelFrame(center, text="Ações", padding=8)
        table_wrap.pack(fill="both", expand=True)

        columns = ("n", "acao", "detalhe", "duracao", "depois")
        self.tree = ttk.Treeview(table_wrap, columns=columns, show="headings", selectmode="browse")
        labels = {"n": "#", "acao": "Ação", "detalhe": "Detalhe", "duracao": "Duração", "depois": "Pausa"}
        widths = {"n": 48, "acao": 190, "detalhe": 430, "duracao": 90, "depois": 82}
        for col in columns:
            self.tree.heading(col, text=labels[col])
            self.tree.column(col, width=widths[col], anchor="center" if col in {"n", "duracao", "depois"} else "w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self.edit_action())

        capture = ttk.LabelFrame(outer, text="Captura", padding=0)
        capture.pack(fill="x", pady=(12, 0))

        self.capture_canvas = tk.Canvas(
            capture,
            height=225,
            highlightthickness=0,
            borderwidth=0,
            background="#FEFEFE",
        )
        self.capture_scrollbar = ttk.Scrollbar(
            capture,
            orient="vertical",
            command=self.capture_canvas.yview,
        )
        self.capture_canvas.configure(yscrollcommand=self.capture_scrollbar.set)

        self.capture_scrollbar.pack(side="right", fill="y")
        self.capture_canvas.pack(side="left", fill="both", expand=True)

        capture_inner = ttk.Frame(self.capture_canvas, padding=12, style="App.TFrame")
        self.capture_inner = capture_inner
        self._capture_window_id = self.capture_canvas.create_window((0, 0), window=capture_inner, anchor="nw")

        def _sync_capture_scrollregion(_event=None):
            self.capture_canvas.configure(scrollregion=self.capture_canvas.bbox("all"))

        def _fit_capture_width(event):
            self.capture_canvas.itemconfigure(self._capture_window_id, width=max(1, event.width))
            _sync_capture_scrollregion()

        capture_inner.bind("<Configure>", _sync_capture_scrollregion)
        self.capture_canvas.bind("<Configure>", _fit_capture_width)

        top_capture = ttk.Frame(capture_inner, style="App.TFrame")
        top_capture.pack(fill="x")
        ttk.Label(top_capture, text="Janela:", width=10).pack(side="left")
        self.window_combo = ttk.Combobox(top_capture, textvariable=self.window_var, state="readonly")
        self.window_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ttk.Button(top_capture, text="Atualizar", command=self.refresh_windows, style="Small.TButton").pack(side="left")
        ttk.Checkbutton(top_capture, text="Só navegadores", variable=self.browser_only_var, command=self.refresh_windows).pack(side="left", padx=(10, 0))
        ttk.Button(top_capture, text="Salvar frame teste", command=self.save_test_frame, style="Small.TButton").pack(side="left", padx=(10, 0))

        tab_capture = ttk.Frame(capture_inner, style="App.TFrame")
        tab_capture.pack(fill="x", pady=(10, 0))
        ttk.Label(tab_capture, text="Aba:", width=10).pack(side="left")
        self.chrome_tab_combo = ttk.Combobox(tab_capture, textvariable=self.chrome_tab_var, state="readonly")
        self.chrome_tab_combo.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.chrome_tab_combo.bind("<<ComboboxSelected>>", self._on_chrome_tab_selected)
        ttk.Button(tab_capture, text="Atualizar abas", command=self.refresh_chrome_tabs, style="Small.TButton").pack(side="left")
        ttk.Button(tab_capture, text="Abrir aba escolhida", command=self.activate_selected_chrome_tab, style="Small.TButton").pack(side="left", padx=(8, 0))

        ttk.Separator(capture_inner).pack(fill="x", pady=12)

        bottom_capture = ttk.Frame(capture_inner, style="App.TFrame")
        bottom_capture.pack(fill="x")
        bottom_capture.columnconfigure(0, weight=1)
        bottom_capture.columnconfigure(1, weight=1)

        video_card = ttk.LabelFrame(bottom_capture, text="Vídeo", padding=10)
        video_card.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ttk.Label(video_card, text="Saída", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Entry(video_card, textvariable=self.output_var).grid(row=1, column=0, sticky="ew", pady=(4, 8))
        ttk.Button(video_card, text="Escolher…", command=self.choose_output, style="Small.TButton").grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(4, 8))
        ttk.Label(video_card, text="Resolução", style="Muted.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Combobox(video_card, state="readonly", width=14, textvariable=self.resolution_var, values=("Nativa", "1280×720", "1920×1080")).grid(row=3, column=0, sticky="w", pady=(4, 8))
        ttk.Label(video_card, text="FPS", style="Muted.TLabel").grid(row=2, column=1, sticky="w")
        ttk.Spinbox(video_card, from_=20, to=60, width=6, textvariable=self.fps_var).grid(row=3, column=1, sticky="w", pady=(4, 8))
        ttk.Label(video_card, text="Cursor", style="Muted.TLabel").grid(row=4, column=0, sticky="w")
        ttk.Combobox(video_card, state="readonly", width=12, textvariable=self.cursor_var, values=("ring", "dot", "hidden")).grid(row=5, column=0, sticky="w", pady=(4, 0))
        ttk.Checkbutton(video_card, text="Efeito de clique", variable=self.show_clicks_var).grid(row=5, column=1, sticky="w", pady=(4, 0))
        video_card.columnconfigure(0, weight=1)

        prep_card = ttk.LabelFrame(bottom_capture, text="Preparação", padding=10)
        prep_card.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        ttk.Checkbutton(prep_card, text="Tela cheia", variable=self.fullscreen_before_record_var).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(prep_card, text="Recarregar animação inicial", variable=self.intro_animation_var).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Label(prep_card, text="Espera da animação", style="Muted.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 0))
        wait_row = ttk.Frame(prep_card, style="App.TFrame")
        wait_row.grid(row=3, column=0, sticky="w", pady=(4, 8))
        ttk.Spinbox(wait_row, from_=0.5, to=15.0, increment=0.5, width=6, textvariable=self.intro_animation_wait_var).pack(side="left")
        ttk.Label(wait_row, text="s", style="Muted.TLabel").pack(side="left", padx=(4, 0))
        ttk.Label(prep_card, text="Contagem inicial", style="Muted.TLabel").grid(row=4, column=0, sticky="w", pady=(4, 0))
        ttk.Spinbox(prep_card, from_=0, to=10, width=6, textvariable=self.countdown_var).grid(row=5, column=0, sticky="w", pady=(4, 8))
        ttk.Label(prep_card, text="Transição padrão", style="Muted.TLabel").grid(row=6, column=0, sticky="w")
        ttk.Combobox(prep_card, state="readonly", width=14, textvariable=self.transition_var, values=("crossfade", "zoom", "slide")).grid(row=7, column=0, sticky="w", pady=(4, 0))

        self.status_frame = tk.Frame(outer, bg="#06152d", highlightthickness=1, highlightbackground="#dce4ef")
        self.status_frame.pack(fill="x", pady=(12, 0))
        self.status_label = tk.Label(
            self.status_frame,
            textvariable=self.status_var,
            bg="#06152d",
            fg="#ffffff",
            padx=12,
            pady=8,
        )
        self.status_label.pack(side="left")
        self.status_help_label = tk.Label(
            self.status_frame,
            text="Emergência: mouse no canto superior esquerdo ou F8.",
            bg="#06152d",
            fg="#c9d4e6",
            padx=12,
            pady=8,
        )
        self.status_help_label.pack(side="right")

    def _pointer_is_over_tools(self) -> bool:
        canvas = getattr(self, "tools_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return False
        try:
            px, py = self.winfo_pointerxy()
            left = canvas.winfo_rootx()
            top = canvas.winfo_rooty()
            right = left + canvas.winfo_width()
            bottom = top + canvas.winfo_height()
            return left <= px < right and top <= py < bottom
        except tk.TclError:
            return False

    def _on_tools_mousewheel(self, event):
        """Rola somente a coluna de ações quando o cursor está sobre ela."""
        if not self._pointer_is_over_tools():
            return None

        canvas = getattr(self, "tools_canvas", None)
        if canvas is None:
            return None

        # Linux/X11 usa Button-4 e Button-5.
        button = getattr(event, "num", None)
        if button == 4:
            step = -2
        elif button == 5:
            step = 2
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None

            if platform.system() == "Darwin":
                # Trackpad/rodinha do macOS costuma enviar deltas pequenos e
                # frequentes. Um passo por evento dá sensação natural.
                magnitude = max(1, min(4, int(abs(delta))))
                step = -magnitude if delta > 0 else magnitude
            else:
                # Windows normalmente envia múltiplos de 120.
                units = int(abs(delta) / 120) or 1
                step = -units if delta > 0 else units

        canvas.yview_scroll(step, "units")
        return "break"


    def _pointer_is_over_capture(self) -> bool:
        canvas = getattr(self, "capture_canvas", None)
        if canvas is None or not canvas.winfo_exists():
            return False
        try:
            px, py = self.winfo_pointerxy()
            left = canvas.winfo_rootx()
            top = canvas.winfo_rooty()
            right = left + canvas.winfo_width()
            bottom = top + canvas.winfo_height()
            return left <= px < right and top <= py < bottom
        except tk.TclError:
            return False

    def _on_capture_mousewheel(self, event):
        """Rola somente a área Captura quando o ponteiro está sobre ela."""
        if not self._pointer_is_over_capture():
            return None

        canvas = getattr(self, "capture_canvas", None)
        if canvas is None:
            return None

        button = getattr(event, "num", None)
        if button == 4:
            step = -2
        elif button == 5:
            step = 2
        else:
            delta = getattr(event, "delta", 0)
            if not delta:
                return None

            if platform.system() == "Darwin":
                magnitude = max(1, min(4, int(abs(delta))))
                step = -magnitude if delta > 0 else magnitude
            else:
                units = int(abs(delta) / 120) or 1
                step = -units if delta > 0 else units

        canvas.yview_scroll(step, "units")
        return "break"

    def refresh_all_sources(self):
        self.refresh_windows()
        self.refresh_chrome_tabs()

    def current_chrome_tab(self) -> ChromeTab | None:
        if not hasattr(self, "chrome_tab_combo"):
            return None
        idx = self.chrome_tab_combo.current()

        # V2.6: "Usar aba atualmente ativa" agora resolve uma aba real.
        if idx == 0:
            return get_active_chrome_tab()

        if idx < 0:
            return None
        real = idx - 1
        if real < 0 or real >= len(self.chrome_tabs):
            return None
        return self.chrome_tabs[real]

    def refresh_chrome_tabs(self):
        if platform.system() != "Darwin":
            self.chrome_tabs = []
            self.chrome_tab_combo["values"] = ("— seleção de abas disponível no macOS —",)
            self.chrome_tab_combo.current(0)
            return
        previous = self.chrome_tab_var.get()
        self.chrome_tabs = list_chrome_tabs()
        values = ["— Usar aba atualmente ativa —"] + [t.label for t in self.chrome_tabs]
        self.chrome_tab_combo["values"] = values
        if previous in values:
            self.chrome_tab_combo.current(values.index(previous))
        else:
            self.chrome_tab_combo.current(0)
        if self.chrome_tabs:
            self.status_var.set(f"{len(self.chrome_tabs)} aba(s) do Chrome encontrada(s).")

    def _on_chrome_tab_selected(self, _event=None):
        if self.current_chrome_tab() is not None:
            self.activate_selected_chrome_tab()

    def _select_front_chrome_window(self) -> WindowInfo | None:
        # Quartz devolve as janelas em ordem de frente para trás. Depois de
        # ativar a aba, a primeira janela do Chrome tende a ser a correta.
        self.windows = list_windows(self.browser_only_var.get())
        self.window_combo["values"] = [w.label for w in self.windows]
        chrome_idx = None
        for i, w in enumerate(self.windows):
            if "google chrome" in f"{w.owner} {w.title}".lower():
                chrome_idx = i
                break
        if chrome_idx is not None:
            self.window_combo.current(chrome_idx)
            return self.windows[chrome_idx]
        if self.windows:
            self.window_combo.current(0)
            return self.windows[0]
        return None

    def activate_selected_chrome_tab(self) -> WindowInfo | None:
        tab = self.current_chrome_tab()
        if tab is None:
            return self.current_window()
        ok, error = activate_chrome_tab(tab)
        if not ok:
            messagebox.showerror(
                APP_NAME,
                "Não consegui abrir a aba escolhida.\n\n"
                "No macOS, permita que Python/Terminal controle o Google Chrome em "
                "Ajustes do Sistema → Privacidade e Segurança → Automação.\n\n"
                f"Detalhe: {error}"
            )
            return None
        time.sleep(0.25)
        resolved = self._select_front_chrome_window()
        self.status_var.set(f"Aba pronta: {tab.title or tab.url}")
        return resolved

    def current_window(self) -> WindowInfo | None:
        idx = self.window_combo.current()
        if idx < 0 or idx >= len(self.windows):
            return None
        return self.windows[idx]

    def recording_config(self) -> RecordingConfig:
        w = h = None
        if self.resolution_var.get() == "1280×720":
            w, h = 1280, 720
        elif self.resolution_var.get() == "1920×1080":
            w, h = 1920, 1080
        return RecordingConfig(
            fps=self.fps_var.get(),
            output_width=w,
            output_height=h,
            cursor_style=self.cursor_var.get(),
            show_clicks=self.show_clicks_var.get(),
            countdown=self.countdown_var.get(),
        ).normalized()

    def apply_recording_config(self, config: RecordingConfig) -> None:
        self.fps_var.set(config.fps)
        self.cursor_var.set(config.cursor_style)
        self.show_clicks_var.set(config.show_clicks)
        self.countdown_var.set(config.countdown)
        if (config.output_width, config.output_height) == (1280, 720):
            self.resolution_var.set("1280×720")
        elif (config.output_width, config.output_height) == (1920, 1080):
            self.resolution_var.set("1920×1080")
        else:
            self.resolution_var.set("Nativa")

    def refresh_windows(self):
        self.status_var.set("Procurando janelas…")
        self.update_idletasks()
        self.windows = list_windows(self.browser_only_var.get())
        self.window_combo["values"] = [w.label for w in self.windows]
        if self.windows:
            self.window_combo.current(0)
            self.status_var.set(f"{len(self.windows)} janela(s) encontrada(s).")
        else:
            self.window_var.set("")
            self.status_var.set("Nenhuma janela compatível encontrada. Verifique permissões do sistema.")

    def choose_output(self):
        path = filedialog.asksaveasfilename(title="Salvar gravação", defaultextension=".mp4", filetypes=[("Vídeo MP4", "*.mp4")])
        if path:
            self.output_var.set(path)

    def save_test_frame(self):
        window = self.current_window()
        if not window:
            messagebox.showwarning(APP_NAME, "Escolha uma janela primeiro.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("Imagem PNG", "*.png")])
        if not path:
            return
        try:
            import cv2
            recorder = ScreenRecorder(window, "unused.mp4", self.recording_config())
            frame = recorder.capture()
            if not cv2.imwrite(path, frame):
                raise RuntimeError("Falha ao salvar PNG")
            self.status_var.set(f"Frame salvo: {path}")
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"Não foi possível capturar o frame:\n{exc}")

    def _timeline_expected_scroll_y(self, page_url: str | None = None) -> float:
        """Infere em que Y do documento a timeline estará antes da próxima captura."""
        for action in reversed(self.actions):
            if page_url and action.page_url and action.page_url != page_url:
                # Se a timeline terminou em outra página, uma posição antiga da
                # mesma URL mais atrás não representa o estado atual.
                return 0.0
            if action.target_scroll_y is not None:
                return max(0.0, float(action.target_scroll_y))
            if action.type == "reload":
                return 0.0
        return 0.0

    @staticmethod
    def _site_scroll_duration(distance_px: float, viewport_height: float) -> float:
        """Calcula um tempo cinematográfico de scroll proporcional à distância."""
        distance = abs(float(distance_px))
        viewport = max(320.0, float(viewport_height or 800.0))
        pages = distance / viewport
        # Curto não fica brusco; longo não vira um vídeo interminável.
        return max(0.55, min(4.80, 0.48 + pages * 0.72))

    def _capture_point(self, action_type: str, name: str):
        tab = self.current_chrome_tab()
        if tab is not None:
            # Ao clicar em "capturar", traz a aba para frente para o usuário só
            # precisar posicionar o mouse no elemento desejado.
            window = self.activate_selected_chrome_tab()
        else:
            window = self.current_window()
        if not window:
            messagebox.showwarning(APP_NAME, "Escolha uma janela/aba primeiro.")
            return

        self.status_var.set("Leve o mouse até o alvo. A posição será salva dentro do site.")
        transition = self.transition_var.get()

        def worker():
            import pyautogui
            for n in (3, 2, 1):
                self.after(0, self.capture_countdown_var.set, f"Capturando em {n}…")
                time.sleep(1)
            x, y = pyautogui.position()
            xr = (x - window.left) / max(1, window.width)
            yr = (y - window.top) / max(1, window.height)
            if not (0 <= xr <= 1 and 0 <= yr <= 1):
                self.after(0, messagebox.showerror, APP_NAME, "O mouse ficou fora da janela selecionada.")
                self.after(0, self.capture_countdown_var.set, "")
                return

            site_data = None
            site_error = ""
            if tab is not None:
                ok, site_data, site_error = capture_site_point(tab, x, y)
                if not ok:
                    site_data = None
                    self.after(0, self.capture_countdown_var.set, "")
                    self.after(
                        0,
                        messagebox.showerror,
                        APP_NAME,
                        "Não consegui salvar esse ponto dentro do site.\n\n"
                        "A ação NÃO foi adicionada para evitar um clique errado.\n\n"
                        "Verifique se o Chrome permite JavaScript de eventos da Apple e tente novamente.\n\n"
                        f"Detalhe: {site_error}",
                    )
                    self.after(0, self.status_var.set, "Captura cancelada: alvo do site não pôde ser identificado.")
                    return

            common = dict(
                type=action_type, name=name, x_rel=xr, y_rel=yr,
                duration=1.2 if action_type == "focus" else 0.75,
                transition=transition,
                zoom=1.20 if action_type == "focus" else 1.18,
                pause_after=0.0 if action_type == "focus" else 0.08,
            )

            additions: list[Action] = []
            if site_data:
                target_y = float(site_data.get("target_scroll_y") or 0.0)
                viewport_h = float(site_data.get("viewport_height") or 800.0)
                page_url = str(site_data.get("url") or "")
                previous_y = self._timeline_expected_scroll_y(page_url)
                distance = target_y - previous_y
                doc_y = float(site_data.get("doc_y") or 0.0)

                predicted_viewport_y = doc_y - previous_y
                safe_top = viewport_h * 0.16
                safe_bottom = viewport_h * 0.84
                needs_scroll = (
                    predicted_viewport_y < safe_top
                    or predicted_viewport_y > safe_bottom
                    or abs(distance) >= 36.0
                )

                if needs_scroll:
                    scroll_duration = self._site_scroll_duration(distance, viewport_h)
                    direction = "baixo" if distance > 0 else "cima"
                    if abs(distance) < 1:
                        direction = "ajustar"
                    additions.append(Action(
                        type="site_scroll",
                        name=f"Scroll automático para {direction}",
                        duration=scroll_duration,
                        pause_after=0.05,
                        target_scroll_y=target_y,
                        capture_scroll_y=previous_y,
                        viewport_height=viewport_h,
                        doc_height=float(site_data.get("doc_height") or 0.0),
                        page_url=page_url,
                    ))

                common.update(
                    selector=str(site_data.get("selector") or "") or None,
                    element_label=str(site_data.get("label") or "") or None,
                    element_kind=str(site_data.get("kind") or "") or None,
                    doc_x=float(site_data.get("doc_x") or 0.0),
                    doc_y=float(site_data.get("doc_y") or 0.0),
                    capture_scroll_y=float(site_data.get("capture_scroll_y") or 0.0),
                    target_scroll_y=target_y,
                    viewport_height=viewport_h,
                    doc_height=float(site_data.get("doc_height") or 0.0),
                    element_offset_x=float(site_data.get("element_offset_x") or 0.5),
                    element_offset_y=float(site_data.get("element_offset_y") or 0.5),
                    page_url=page_url,
                )

            action = Action(**common)
            additions.append(action)
            self.actions.extend(additions)
            self.after(0, self.capture_countdown_var.set, "")
            self.after(0, self.refresh_actions)

            if site_data:
                doc_y = float(site_data.get("doc_y") or 0.0)
                scroll_count = len(additions) - 1
                msg = f"{name} salvo no site em Y {doc_y:.0f}px"
                if scroll_count:
                    msg += " · scroll automático adicionado"
                self.after(0, self.status_var.set, msg)
            else:
                warning = "Ação salva em modo tela"
                if site_error:
                    warning += f" · DOM indisponível: {site_error}"
                self.after(0, self.status_var.set, warning)

        threading.Thread(target=worker, daemon=True).start()

    def repair_target_scrolls(self):
        """Insere scrolls faltantes antes de ações page-aware já existentes."""
        if not self.actions:
            messagebox.showinfo(APP_NAME, "A timeline está vazia.")
            return

        rebuilt: list[Action] = []
        expected_by_url: dict[str, float] = {}
        inserted = 0
        screen_only = 0

        for action in self.actions:
            page_key = action.page_url or "__default__"

            if action.type == "reload":
                expected_by_url[page_key] = 0.0
                rebuilt.append(action)
                continue

            if action.type == "site_scroll":
                rebuilt.append(action)
                if action.target_scroll_y is not None:
                    expected_by_url[page_key] = max(0.0, float(action.target_scroll_y))
                continue

            is_target_action = action.type in {"smart_click", "click", "move", "focus"}
            if is_target_action:
                if action.doc_y is None or action.target_scroll_y is None:
                    screen_only += 1
                    rebuilt.append(action)
                    continue

                previous_y = expected_by_url.get(page_key, 0.0)
                viewport_h = max(320.0, float(action.viewport_height or 800.0))
                target_y = max(0.0, float(action.target_scroll_y))
                predicted_vy = float(action.doc_y) - previous_y
                distance = target_y - previous_y
                needs_scroll = (
                    predicted_vy < viewport_h * 0.16
                    or predicted_vy > viewport_h * 0.84
                    or abs(distance) >= 36.0
                )

                previous_action = rebuilt[-1] if rebuilt else None
                already_has_scroll = (
                    previous_action is not None
                    and previous_action.type == "site_scroll"
                    and previous_action.target_scroll_y is not None
                    and abs(float(previous_action.target_scroll_y) - target_y) < 8.0
                )

                if needs_scroll and not already_has_scroll:
                    direction = "baixo" if distance > 0 else "cima"
                    if abs(distance) < 1:
                        direction = "ajustar"
                    rebuilt.append(Action(
                        type="site_scroll",
                        name=f"Scroll automático para {direction}",
                        duration=self._site_scroll_duration(distance, viewport_h),
                        pause_after=0.05,
                        target_scroll_y=target_y,
                        capture_scroll_y=previous_y,
                        viewport_height=viewport_h,
                        doc_height=action.doc_height,
                        page_url=action.page_url,
                    ))
                    inserted += 1

                expected_by_url[page_key] = target_y

            rebuilt.append(action)

        self.actions = rebuilt
        self.refresh_actions()

        msg = f"{inserted} scroll(s) automático(s) inserido(s)."
        if screen_only:
            msg += (
                f"\n\n{screen_only} ação(ões) antiga(s) estão salvas apenas como coordenada de tela "
                "e não podem ser reparadas automaticamente. Recapture essas ações na V2.6."
            )
        self.status_var.set(msg.replace("\n", " · "))
        messagebox.showinfo(APP_NAME, msg)

    def capture_smart_click(self):
        self._capture_point("smart_click", "Clique inteligente")

    def capture_click(self):
        self._capture_point("click", "Clique suave")

    def capture_move(self):
        self._capture_point("move", "Mover cursor")

    def capture_focus(self):
        self._capture_point("focus", "Foco de câmera")

    def add_scroll(self, amount: int):
        direction = "para baixo" if amount < 0 else "para cima"
        self.actions.append(Action(type="scroll", name=f"Scroll {direction}", amount=amount, duration=1.35))
        self.refresh_actions()

    def add_wait(self):
        seconds = simpledialog.askfloat(APP_NAME, "Quantos segundos?", initialvalue=1.0, minvalue=0.1, maxvalue=30.0)
        if seconds is not None:
            self.actions.append(Action(type="wait", name="Pausa", duration=seconds, pause_after=0.0))
            self.refresh_actions()

    def add_type(self):
        text = simpledialog.askstring(APP_NAME, "Texto para digitar:")
        if text:
            self.actions.append(Action(type="type_text", name="Digitar texto", text=text, duration=0.9))
            self.refresh_actions()

    def add_hotkey(self):
        raw = simpledialog.askstring(APP_NAME, "Atalho (ex.: ctrl+l ou command+l):")
        if raw:
            keys = [k.strip().lower() for k in raw.replace("+", " ").split() if k.strip()]
            self.actions.append(Action(type="hotkey", name="Atalho", keys=keys, duration=0.1))
            self.refresh_actions()

    def _auto_tour_options_dialog(self) -> TourOptions | None:
        dialog = tk.Toplevel(self)
        dialog.title("Tour automático do site")
        dialog.transient(self)
        dialog.resizable(False, False)
        dialog.grab_set()

        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Antes de analisar o site", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text="Marque como você quer que o tour seja criado. A análise lê a estrutura da aba escolhida do Chrome.",
            wraplength=520,
        ).pack(anchor="w", pady=(4, 12))

        reload_var = tk.BooleanVar(value=True)
        intro_var = tk.BooleanVar(value=True)
        intro_wait_var = tk.DoubleVar(value=2.5)
        sections_var = tk.BooleanVar(value=True)
        ctas_var = tk.BooleanVar(value=True)
        clicks_var = tk.BooleanVar(value=False)
        focus_var = tk.BooleanVar(value=True)
        pauses_var = tk.BooleanVar(value=True)
        max_points_var = tk.IntVar(value=16)

        ttk.Checkbutton(frame, text="Recarregar a página com ⌘R antes de começar a gravação", variable=reload_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="O site tem animação de entrada/carregamento", variable=intro_var).pack(anchor="w", pady=2)

        waitrow = ttk.Frame(frame)
        waitrow.pack(fill="x", pady=(2, 8))
        ttk.Label(waitrow, text="Tempo para mostrar a animação inicial:").pack(side="left", padx=(24, 6))
        ttk.Spinbox(waitrow, from_=0.8, to=12.0, increment=0.25, width=6, textvariable=intro_wait_var).pack(side="left")
        ttk.Label(waitrow, text="segundos").pack(side="left", padx=(5, 0))

        ttk.Separator(frame).pack(fill="x", pady=8)
        ttk.Checkbutton(frame, text="Identificar títulos, seções e rodapé automaticamente", variable=sections_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="Identificar botões e CTAs automaticamente", variable=ctas_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="Clicar automaticamente somente em CTAs classificados como seguros", variable=clicks_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="Aplicar foco/zoom cinematográfico nos elementos", variable=focus_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(frame, text="Adicionar pequenas pausas entre os pontos", variable=pauses_var).pack(anchor="w", pady=2)

        maxrow = ttk.Frame(frame)
        maxrow.pack(fill="x", pady=(8, 2))
        ttk.Label(maxrow, text="Máximo de pontos no tour:").pack(side="left")
        ttk.Spinbox(maxrow, from_=4, to=30, width=5, textvariable=max_points_var).pack(side="left", padx=6)

        ttk.Label(
            frame,
            text=("Para a identificação automática, o Chrome pode exigir: Visualizar → Desenvolvedor → "
                  "Permitir JavaScript de eventos da Apple. Isso só é usado para ler os elementos da aba e rolar até eles."),
            wraplength=520,
        ).pack(anchor="w", pady=(10, 10))

        result: dict[str, TourOptions | None] = {"value": None}

        def confirm():
            if not sections_var.get() and not ctas_var.get():
                messagebox.showwarning(APP_NAME, "Marque pelo menos seções/títulos ou botões/CTAs.", parent=dialog)
                return
            result["value"] = TourOptions(
                reload_before=reload_var.get(),
                has_intro_animation=intro_var.get(),
                intro_wait=float(intro_wait_var.get()),
                include_sections=sections_var.get(),
                include_ctas=ctas_var.get(),
                click_safe_ctas=clicks_var.get(),
                camera_focus=focus_var.get(),
                add_pauses=pauses_var.get(),
                max_points=int(max_points_var.get()),
                transition=transition,
            )
            dialog.destroy()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Cancelar", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Analisar e gerar tour", command=confirm).pack(side="right", padx=(0, 8))

        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        return result["value"]

    def generate_automatic_tour(self):
        tab = self.current_chrome_tab()
        if tab is None:
            messagebox.showwarning(
                APP_NAME,
                "Escolha uma aba específica em ‘Aba do Chrome’ antes de gerar o tour automático."
            )
            return

        if self.activate_selected_chrome_tab() is None:
            return

        options = self._auto_tour_options_dialog()
        if options is None:
            return

        replace_existing = True
        if self.actions:
            replace_existing = messagebox.askyesno(
                APP_NAME,
                "A timeline já tem ações.\n\nSim = substituir pelo tour automático\nNão = adicionar o tour ao final",
            )

        self.status_var.set("Analisando títulos, seções, botões e CTAs da aba…")
        self.auto_tour_button.configure(state="disabled", text="ANALISANDO SITE…")

        def worker():
            ok, analysis, error = inspect_chrome_site(tab)
            if not ok or analysis is None:
                self.after(0, self._automatic_tour_failed, error)
                return
            new_actions = build_tour_actions(analysis, options)
            structural = sum(1 for e in analysis.elements if e.kind in {"heading", "section", "main", "footer"})
            interactive = sum(1 for e in analysis.elements if e.kind in {"button", "link"})
            self.after(0, self._automatic_tour_ready, new_actions, replace_existing, structural, interactive, analysis.title)

        threading.Thread(target=worker, daemon=True).start()

    def _automatic_tour_failed(self, error: str):
        self.auto_tour_button.configure(state="normal", text="Gerar tour automático")
        self.status_var.set("Não foi possível analisar a aba.")
        messagebox.showerror(APP_NAME, f"Não consegui analisar o site automaticamente.\n\n{error}")

    def _automatic_tour_ready(self, new_actions: list[Action], replace_existing: bool, structural: int, interactive: int, title: str):
        self.auto_tour_button.configure(state="normal", text="Gerar tour automático")
        if replace_existing:
            self.actions = new_actions
        else:
            self.actions.extend(new_actions)
        self.refresh_actions()
        auto_points = sum(1 for a in new_actions if a.type == "dom_visit")
        safe_clicks = sum(1 for a in new_actions if a.type == "dom_visit" and a.auto_click)
        self.status_var.set(
            f"Tour automático pronto: {auto_points} pontos · {safe_clicks} clique(s) automático(s)."
        )
        messagebox.showinfo(
            APP_NAME,
            f"Tour criado para: {title or 'aba atual'}\n\n"
            f"Elementos encontrados: {structural} estruturais + {interactive} interativos\n"
            f"Pontos adicionados à timeline: {auto_points}\n"
            f"Cliques automáticos seguros: {safe_clicks}\n\n"
            "Agora é só clicar em INICIAR GRAVAÇÃO.",
        )

    def generate_continuous_full_page_scroll(self):
        tab = self.current_chrome_tab()
        if tab is None:
            messagebox.showwarning(
                APP_NAME,
                "Escolha uma aba do Chrome antes de criar o scroll contínuo."
            )
            return

        if self.activate_selected_chrome_tab() is None:
            return

        replace_existing = True
        if self.actions:
            replace_existing = messagebox.askyesno(
                APP_NAME,
                "A timeline já tem ações.\n\n"
                "Sim = substituir tudo pelo scroll contínuo da página inteira\n"
                "Não = adicionar ao final",
            )

        self.status_var.set("Medindo a página para criar um scroll contínuo…")
        self.continuous_scroll_button.configure(state="disabled", text="Medindo página…")

        def worker():
            ok, analysis, error = inspect_chrome_site(tab)
            if not ok or analysis is None:
                self.after(0, self._continuous_scroll_failed, error)
                return

            # Mede mais de uma vez antes de calcular a estimativa inicial.
            # Isso pega imagens/fontes/componentes que alteram a altura logo
            # depois da primeira leitura.
            measured_heights = [max(0.0, float(analysis.doc_height))]
            measured_viewports = [max(320.0, float(analysis.viewport_height or 800))]
            for _ in range(3):
                ok_state, state, _ = get_page_scroll_state(tab)
                if ok_state and state:
                    measured_heights.append(max(0.0, float(state.get("doc_height", 0.0))))
                    measured_viewports.append(max(320.0, float(state.get("viewport_height", 800.0))))
                time.sleep(0.12)

            doc_h = max(measured_heights)
            viewport_h = measured_viewports[-1]
            max_scroll = max(0.0, doc_h - viewport_h)

            speed = 460.0
            if max_scroll <= 8:
                duration = 1.0
            else:
                # Apenas estimativa visual para a timeline. A execução real
                # não possui deadline fixo e pode ficar mais longa se a página crescer.
                duration = max_scroll / speed + 1.0

            action = Action(
                type="continuous_scroll",
                name="Scroll contínuo · página inteira",
                duration=duration,
                pause_after=0.0,
                capture_scroll_y=0.0,
                target_scroll_y=max_scroll,
                viewport_height=viewport_h,
                doc_height=doc_h,
                page_url=analysis.url,
                scroll_speed=speed,
            )
            self.after(
                0,
                self._continuous_scroll_ready,
                action,
                replace_existing,
                analysis.title,
                int(doc_h),
                int(viewport_h),
            )

        threading.Thread(target=worker, daemon=True).start()

    def _continuous_scroll_failed(self, error: str):
        self.continuous_scroll_button.configure(
            state="normal", text="Scroll contínuo da página"
        )
        self.status_var.set("Não foi possível medir a página.")
        messagebox.showerror(
            APP_NAME,
            "Não consegui medir a página para criar o scroll contínuo.\n\n" + str(error),
        )

    def _continuous_scroll_ready(
        self,
        action: Action,
        replace_existing: bool,
        title: str,
        doc_height: int,
        viewport_height: int,
    ):
        self.continuous_scroll_button.configure(
            state="normal", text="Scroll contínuo da página"
        )
        if replace_existing:
            self.actions = [action]
        else:
            self.actions.append(action)
        self.refresh_actions()

        distance = max(0, doc_height - viewport_height)
        self.status_var.set(
            f"Scroll contínuo pronto · {distance}px · {action.duration:.1f}s · sem pausas."
        )
        messagebox.showinfo(
            APP_NAME,
            f"Scroll contínuo criado para: {title or 'aba atual'}\n\n"
            f"Altura da página: {doc_height:,} px\n"
            f"Distância percorrida: {distance:,} px\n"
            f"Tempo estimado inicial: {action.duration:.1f} s\n"
            f"Velocidade: {action.scroll_speed or 460:.0f} px/s\n\n"
            "O rodapé é recalculado durante o movimento. Se a página aumentar, o vídeo fica mais longo em vez de acelerar de repente.",
        )

    def generate_full_page_scroll_tour(self):
        tab = self.current_chrome_tab()
        if tab is None:
            messagebox.showwarning(
                APP_NAME,
                "Escolha uma aba específica em ‘Aba do Chrome’ antes de gerar o tour da página inteira."
            )
            return

        if self.activate_selected_chrome_tab() is None:
            return

        replace_existing = True
        if self.actions:
            replace_existing = messagebox.askyesno(
                APP_NAME,
                "A timeline já tem ações.\n\n"
                "Sim = substituir por um tour completo do topo ao rodapé\n"
                "Não = adicionar o tour ao final",
            )

        self.status_var.set("Medindo altura da página e calculando o scroll cinematográfico…")
        self.full_page_tour_button.configure(state="disabled", text="Medindo página…")

        def worker():
            ok, analysis, error = inspect_chrome_site(tab)
            if not ok or analysis is None:
                self.after(0, self._full_page_tour_failed, error)
                return

            options = FullPageScrollOptions()
            new_actions = build_full_page_scroll_tour(analysis, options)
            self.after(
                0,
                self._full_page_tour_ready,
                new_actions,
                replace_existing,
                analysis.title,
                analysis.doc_height,
                analysis.viewport_height,
            )

        threading.Thread(target=worker, daemon=True).start()

    def _full_page_tour_failed(self, error: str):
        self.full_page_tour_button.configure(state="normal", text="Tour da página inteira")
        self.status_var.set("Não foi possível medir a página.")
        messagebox.showerror(
            APP_NAME,
            "Não consegui medir a página para criar o tour completo.\n\n" + str(error)
        )

    def _full_page_tour_ready(
        self,
        new_actions: list[Action],
        replace_existing: bool,
        title: str,
        doc_height: int,
        viewport_height: int,
    ):
        self.full_page_tour_button.configure(state="normal", text="Tour da página inteira")
        if replace_existing:
            self.actions = new_actions
        else:
            self.actions.extend(new_actions)
        self.refresh_actions()

        scrolls = [a for a in new_actions if a.type == "site_scroll"]
        scroll_seconds = sum(a.duration + a.pause_after for a in scrolls)
        max_scroll = max(0, int(doc_height) - int(viewport_height))
        self.status_var.set(
            f"Tour completo pronto: página {doc_height}px · {len(scrolls)} trecho(s) · {scroll_seconds:.1f}s de scroll."
        )
        messagebox.showinfo(
            APP_NAME,
            f"Tour da página inteira criado para: {title or 'aba atual'}\n\n"
            f"Altura total: {int(doc_height):,} px\n"
            f"Área visível: {int(viewport_height):,} px\n"
            f"Distância até o rodapé: {max_scroll:,} px\n"
            f"Trechos cinematográficos: {len(scrolls)}\n"
            f"Tempo de scroll: {scroll_seconds:.1f} s\n\n"
            "O DemoFlow começa no topo e percorre a página inteira até o rodapé.",
        )

    def generate_scroll_tour(self):
        additions = [
            Action(type="wait", name="Pausa inicial", duration=0.8, pause_after=0.0),
            Action(type="scroll", name="Scroll cinematográfico 1", amount=-7, duration=1.35),
            Action(type="wait", name="Respirar", duration=0.55, pause_after=0.0),
            Action(type="scroll", name="Scroll cinematográfico 2", amount=-7, duration=1.45),
            Action(type="wait", name="Respirar", duration=0.55, pause_after=0.0),
            Action(type="scroll", name="Scroll cinematográfico 3", amount=-7, duration=1.35),
        ]
        self.actions.extend(additions)
        self.refresh_actions()
        self.status_var.set("Tour de scroll adicionado à timeline.")

    def detail_for(self, a: Action) -> str:
        if a.type in ("smart_click", "click", "move"):
            trans = f" · {a.transition}" if a.type == "smart_click" else ""
            if a.doc_y is not None:
                label = f" · {a.element_label}" if a.element_label else ""
                if len(label) > 38:
                    label = label[:35] + "…"
                return f"site Y {a.doc_y:.0f}px{label}{trans}"
            return f"tela {a.x_rel:.3f}, {a.y_rel:.3f}{trans}"
        if a.type == "focus":
            if a.doc_y is not None:
                return f"site Y {a.doc_y:.0f}px · zoom {a.zoom:.2f}×"
            return f"centro {a.x_rel:.3f}, {a.y_rel:.3f} · zoom {a.zoom:.2f}×"
        if a.type == "scroll":
            return f"{a.amount} passos"
        if a.type == "site_scroll":
            current = a.capture_scroll_y if a.capture_scroll_y is not None else 0.0
            target = a.target_scroll_y if a.target_scroll_y is not None else 0.0
            return f"Y {current:.0f} → {target:.0f}px · página {a.doc_height or 0:.0f}px"
        if a.type == "continuous_scroll":
            current = a.capture_scroll_y if a.capture_scroll_y is not None else 0.0
            target = a.target_scroll_y if a.target_scroll_y is not None else 0.0
            speed = a.scroll_speed or 460.0
            return f"CONTÍNUO · Y {current:.0f} → ~{target:.0f}px · {speed:.0f}px/s · dinâmico"
        if a.type == "wait":
            return "tempo de respiro"
        if a.type == "type_text":
            text = a.text or ""
            return text if len(text) <= 48 else text[:45] + "…"
        if a.type == "hotkey":
            return "+".join(a.keys or [])
        if a.type == "reload":
            return f"⌘R · aguarda {a.duration:.1f}s"
        if a.type == "dom_visit":
            click = " · clique seguro" if a.auto_click else ""
            label = a.element_label or a.selector or "elemento"
            if len(label) > 54:
                label = label[:51] + "…"
            return f"{a.element_kind or 'elemento'} · {label}{click}"
        return ""

    def refresh_actions(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        total = 0.0
        for i, a in enumerate(self.actions, start=1):
            extra = 0.0
            if a.type == "focus":
                extra = 0.92
            elif a.type == "smart_click":
                extra = max(0.12, a.settle) + 0.55
            elif a.type == "dom_visit":
                extra = 0.72 + (0.72 if a.zoom > 1.001 else 0.0) + (0.42 if a.auto_click else 0.0)
            total += max(0.0, a.duration) + max(0.0, a.pause_after) + extra
            self.tree.insert("", "end", values=(i, a.name, self.detail_for(a), f"{a.duration:.2f}s", f"{a.pause_after:.2f}s"))
        total_text = f"{total:.1f}".replace(".", ",")
        count = len(self.actions)
        label = "ação" if count == 1 else "ações"
        self.duration_var.set(f"{count} {label} · {total_text} s")

    def selected_index(self) -> int | None:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return int(vals[0]) - 1

    def edit_action(self):
        idx = self.selected_index()
        if idx is None:
            return
        a = self.actions[idx]
        duration = simpledialog.askfloat(APP_NAME, f"Duração principal de '{a.name}' (s):", initialvalue=a.duration, minvalue=0.05, maxvalue=30.0)
        if duration is None:
            return
        a.duration = duration
        pause = simpledialog.askfloat(APP_NAME, "Pausa após a ação (s):", initialvalue=a.pause_after, minvalue=0.0, maxvalue=10.0)
        if pause is not None:
            a.pause_after = pause
        if a.type == "scroll":
            amount = simpledialog.askinteger(APP_NAME, "Quantidade de scroll (negativo = descer):", initialvalue=a.amount or -8, minvalue=-100, maxvalue=100)
            if amount is not None:
                a.amount = amount
        elif a.type == "site_scroll":
            target = simpledialog.askfloat(APP_NAME, "Posição Y do site (px):", initialvalue=a.target_scroll_y or 0.0, minvalue=0.0)
            if target is not None:
                a.target_scroll_y = target
        elif a.type == "smart_click":
            settle = simpledialog.askfloat(APP_NAME, "Tempo para a página estabilizar após o clique (s):", initialvalue=a.settle, minvalue=0.1, maxvalue=5.0)
            if settle is not None:
                a.settle = settle
            trans = simpledialog.askstring(APP_NAME, "Transição: crossfade, zoom ou slide", initialvalue=a.transition)
            if trans and trans.lower() in {"crossfade", "zoom", "slide"}:
                a.transition = trans.lower()
        elif a.type == "focus":
            zoom = simpledialog.askfloat(APP_NAME, "Zoom (1.05 a 1.80):", initialvalue=a.zoom, minvalue=1.05, maxvalue=1.80)
            if zoom is not None:
                a.zoom = zoom
        elif a.type == "type_text":
            text = simpledialog.askstring(APP_NAME, "Texto:", initialvalue=a.text or "")
            if text is not None:
                a.text = text
        self.refresh_actions()

    def duplicate_action(self):
        idx = self.selected_index()
        if idx is None:
            return
        from copy import deepcopy
        self.actions.insert(idx + 1, deepcopy(self.actions[idx]))
        self.refresh_actions()

    def delete_action(self):
        idx = self.selected_index()
        if idx is not None:
            self.actions.pop(idx)
            self.refresh_actions()

    def clear_actions(self):
        if self.actions and messagebox.askyesno(APP_NAME, "Limpar toda a timeline?"):
            self.actions.clear()
            self.refresh_actions()

    def move_action(self, delta: int):
        idx = self.selected_index()
        if idx is None:
            return
        new = idx + delta
        if 0 <= new < len(self.actions):
            self.actions[idx], self.actions[new] = self.actions[new], self.actions[idx]
            self.refresh_actions()
            item = self.tree.get_children()[new]
            self.tree.selection_set(item)
            self.tree.focus(item)

    def save_script(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("Projeto DemoFlow", "*.json")])
        if path:
            try:
                save_project(path, self.actions, self.recording_config())
                self.status_var.set("Projeto salvo.")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Não foi possível salvar:\n{exc}")

    def load_script(self):
        path = filedialog.askopenfilename(filetypes=[("Projeto DemoFlow", "*.json"), ("JSON", "*.json")])
        if path:
            try:
                project = load_project(path)
                self.actions = project.actions
                self.apply_recording_config(project.recording)
                self.refresh_actions()
                self.status_var.set("Projeto carregado. Projetos da V1 também são aceitos.")
            except Exception as exc:
                messagebox.showerror(APP_NAME, f"Não foi possível abrir:\n{exc}")

    def _run_countdown(self, seconds: int) -> None:
        for n in range(seconds, 0, -1):
            if self.engine and self.engine.stop_event.is_set():
                raise InterruptedError
            self.after(0, self.status_var.set, f"Começando em {n}…")
            time.sleep(1)

    @staticmethod
    def _window_is_effectively_fullscreen(window: WindowInfo) -> bool:
        """Heurística simples para não alternar para FORA se o Chrome já estiver fullscreen."""
        try:
            screen_w, screen_h = pyautogui.size()
            return (
                window.width >= screen_w * 0.93
                and window.height >= screen_h * 0.86
            )
        except Exception:
            return False

    def _fresh_front_browser_window(self, fallback: WindowInfo, browser_only: bool = True) -> WindowInfo:
        """Relê a geometria depois de entrar/sair de tela cheia."""
        try:
            wins = list_windows(browser_only)
            for w in wins:
                hay = f"{w.owner} {w.title}".lower()
                if "google chrome" in hay or "chrome" in hay:
                    return w
            if wins:
                return wins[0]
        except Exception:
            pass
        return fallback

    def _enter_fullscreen_if_needed(self, window: WindowInfo) -> tuple[WindowInfo, bool]:
        """Entra em tela cheia somente se ainda não estiver.

        Retorna (janela_atualizada, alterou_estado).
        """
        if self._window_is_effectively_fullscreen(window):
            return window, False

        self.after(0, self.status_var.set, "Ativando tela cheia…")
        if platform.system() == "Darwin":
            pyautogui.hotkey("ctrl", "command", "f")
        else:
            pyautogui.press("f11")

        time.sleep(1.15)
        fresh = self._fresh_front_browser_window(window, True)
        return fresh, True

    def _exit_fullscreen_if_changed(self, changed: bool) -> None:
        if not changed:
            return
        try:
            if platform.system() == "Darwin":
                pyautogui.hotkey("ctrl", "command", "f")
            else:
                pyautogui.press("f11")
            time.sleep(0.35)
        except Exception:
            pass

    @staticmethod
    def _reload_browser_for_intro() -> None:
        if platform.system() == "Darwin":
            pyautogui.hotkey("command", "r")
        else:
            pyautogui.hotkey("ctrl", "r")

    def start_run(self, record: bool):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo(APP_NAME, "Já existe uma execução em andamento.")
            return

        selected_tab = self.current_chrome_tab()
        window = self.activate_selected_chrome_tab() if selected_tab is not None else self.current_window()
        if not window:
            messagebox.showwarning(APP_NAME, "Escolha uma janela ou uma aba do Chrome.")
            return
        if not self.actions:
            messagebox.showwarning(APP_NAME, "Adicione pelo menos uma ação.")
            return
        if record and not self.output_var.get().strip():
            messagebox.showwarning(APP_NAME, "Escolha o arquivo de saída.")
            return

        config = self.recording_config()
        actions = list(self.actions)
        output = self.output_var.get().strip()

        # Lemos os Tk variables antes de entrar na thread.
        use_fullscreen = bool(self.fullscreen_before_record_var.get())
        has_intro_animation = bool(self.intro_animation_var.get())
        try:
            intro_wait = float(self.intro_animation_wait_var.get())
        except Exception:
            intro_wait = 2.5
        intro_wait = max(0.5, min(15.0, intro_wait))

        # Se um tour antigo já colocou "reload" como primeira ação útil,
        # o novo checkbox assume esse papel para não recarregar duas vezes.
        if has_intro_animation:
            first_non_wait_idx = next(
                (i for i, a in enumerate(actions) if a.type != "wait"),
                None,
            )
            if first_non_wait_idx is not None and actions[first_non_wait_idx].type == "reload":
                actions.pop(first_non_wait_idx)

        def worker():
            fullscreen_changed = False
            run_window = window
            try:
                # 1) Prepara a janela antes da contagem e ANTES de criar o recorder.
                if use_fullscreen:
                    run_window, fullscreen_changed = self._enter_fullscreen_if_needed(run_window)

                self.engine = DemoEngine(run_window, None, chrome_tab=selected_tab)

                # 2) Posiciona no ponto inicial antes da contagem.
                # Para animação de entrada, garantimos topo antes do reload.
                if selected_tab is not None:
                    first_visual = next((a for a in actions if a.type != "wait"), None)

                    if has_intro_animation:
                        scroll_page_to(selected_tab, 0.0, behavior="auto")
                        time.sleep(0.12)
                    elif (
                        first_visual is not None
                        and first_visual.type in {"site_scroll", "continuous_scroll"}
                        and first_visual.capture_scroll_y is not None
                    ):
                        scroll_page_to(
                            selected_tab,
                            float(first_visual.capture_scroll_y),
                            behavior="auto",
                        )
                        time.sleep(0.18)

                # 3) Contagem acontece já em tela cheia.
                self._run_countdown(config.countdown)

                # 4) Inicia o recorder antes do ⌘R para a animação entrar no vídeo.
                if record:
                    self.after(0, self.status_var.set, "Iniciando gravação…")
                    self.recorder = ScreenRecorder(run_window, output, config)
                    self.recorder.start()
                    self.engine.recorder = self.recorder
                    time.sleep(0.25)

                # 5) Se marcado, recarrega e captura a animação de entrada.
                if has_intro_animation:
                    self.after(
                        0,
                        self.status_var.set,
                        f"Recarregando para capturar animação inicial · {intro_wait:.1f}s…",
                    )
                    self._reload_browser_for_intro()
                    time.sleep(intro_wait)

                # 6) Só agora executa a timeline.
                self.engine.on_status = lambda s: self.after(0, self.status_var.set, s)
                self.engine.execute(actions)

                if record:
                    time.sleep(0.55)
                    self.after(0, self.status_var.set, f"Vídeo finalizado: {output}")
                else:
                    self.after(0, self.status_var.set, "Teste concluído sem gravação.")

            except InterruptedError:
                self.after(0, self.status_var.set, "Execução interrompida.")
            except Exception as exc:
                self.after(0, messagebox.showerror, APP_NAME, f"Erro durante a execução:\n{exc}")
                self.after(0, self.status_var.set, "Erro.")
            finally:
                if self.recorder:
                    try:
                        self.recorder.stop()
                    except Exception:
                        pass
                self.recorder = None
                self.engine = None

                # Restaura a janela somente se foi o DemoFlow que entrou em fullscreen.
                if fullscreen_changed:
                    self._exit_fullscreen_if_changed(True)

        self.worker = threading.Thread(target=worker, daemon=True)
        self.worker.start()

    def stop_run(self):
        if self.engine:
            self.engine.stop()
        if self.recorder:
            self.recorder.stop()
        self.status_var.set("Parando…")


if __name__ == "__main__":
    App().mainloop()
