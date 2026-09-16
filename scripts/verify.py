from pathlib import Path
import ast, json, py_compile

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    ROOT / "app.py",
    ROOT / "requirements.txt",
    ROOT / "assets" / "app_icon.png",
    ROOT / "assets" / "app_icon.ico",
    ROOT / "build_macos.command",
    ROOT / "build_windows.bat",
    ROOT / "LICENSE",
    ROOT / "MARCOSDEV.md",
]

errors = []
for path in REQUIRED:
    if not path.exists():
        errors.append(f"arquivo obrigatório ausente: {path.relative_to(ROOT)}")

python_files = sorted(p for p in ROOT.rglob("*.py") if ".venv" not in p.parts and "build" not in p.parts)
for path in python_files:
    try:
        source = path.read_text(encoding="utf-8")
        ast.parse(source, filename=str(path))
        py_compile.compile(str(path), doraise=True)
    except Exception as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")

example = ROOT / "examples" / "demo-project.json"
if example.exists():
    try:
        json.loads(example.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"examples/demo-project.json: {exc}")

if errors:
    print("Falha na verificação:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

print(f"Verificação concluída: {len(python_files)} arquivos Python válidos.")
