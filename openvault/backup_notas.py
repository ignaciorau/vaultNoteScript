import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog

NAME_RE = re.compile(r"[A-Za-z0-9._-]+")


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def check(result, what):
    if result.returncode != 0:
        print(f"Error en {what}:\n{result.stderr.strip()}")
        return False
    return True


def choose_path():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    path = filedialog.askdirectory(title="Elegí la carpeta de tus notas")
    root.destroy()
    return Path(path) if path else None


def ask_name():
    name = input("Nombre del repo: ").strip().replace(" ", "-")
    if name and (name in (".", "..") or not NAME_RE.fullmatch(name)):
        print("Nombre inválido: usá letras, números, '-', '_' o '.'.")
        return ""
    return name


def confirm(question):
    while True:
        answer = input(f"{question} (s/n): ").strip().lower()
        if answer in ("s", "si", "sí"):
            return True
        if answer in ("n", "no"):
            return False
        print("Escribí 's' o 'n'.")


def gh_ready():
    return bool(shutil.which("gh")) and run(["gh", "auth", "status"]).returncode == 0


def get_owner():
    return run(["gh", "api", "user", "-q", ".login"]).stdout.strip()


def repo_exists(owner, name):
    return run(["gh", "repo", "view", f"{owner}/{name}"]).returncode == 0


def guardar(vault, owner, name):
    url = f"https://github.com/{owner}/{name}.git"

    if not (vault / ".git").exists():
        if not check(run(["git", "init", "-b", "main"], cwd=vault), "git init"):
            return False

    gitignore = vault / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".obsidian/workspace*.json\n", encoding="utf-8")

    has_origin = run(["git", "remote", "get-url", "origin"], cwd=vault).returncode == 0
    action = "set-url" if has_origin else "add"
    if not check(run(["git", "remote", action, "origin", url], cwd=vault), "git remote"):
        return False

    if not check(run(["git", "add", "-A"], cwd=vault), "git add"):
        return False

    if run(["git", "diff", "--cached", "--quiet"], cwd=vault).returncode != 0:
        msg = f"auto: {datetime.now():%Y-%m-%d %H:%M}"
        if not check(run(["git", "commit", "-m", msg], cwd=vault), "git commit"):
            return False
    else:
        print("Sin cambios nuevos.")

    return check(run(["git", "push", "-u", "origin", "HEAD"], cwd=vault), "git push")


def main():
    if not shutil.which("git"):
        sys.exit("Falta instalar git.")
    if not gh_ready():
        sys.exit("Instalá GitHub CLI y corré 'gh auth login'.")

    vault = choose_path()
    if not vault:
        print("No elegiste ninguna carpeta.")
        return

    if not (vault / ".obsidian").is_dir():
        if not confirm(f"'{vault}' no parece un vault de Obsidian (no tiene .obsidian). ¿Subirla igual?"):
            print("Cancelado.")
            return

    name = ask_name()
    if not name:
        print("Nombre del repo vacío o inválido.")
        return

    owner = get_owner()
    if not owner:
        sys.exit("No pude obtener tu usuario de GitHub.")

    if not repo_exists(owner, name):
        if not confirm("No se encontró el repo, ¿querés crearlo con ese nombre?"):
            print("Cancelado.")
            return
        if not check(run(["gh", "repo", "create", name, "--private"]), "crear el repo"):
            return

    if guardar(vault, owner, name):
        print(f"Listo: https://github.com/{owner}/{name}")


if __name__ == "__main__":
    main()
