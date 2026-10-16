#!/usr/bin/env python3

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog


def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def check(result, what):
    if result.returncode != 0:
        print(f"Error en {what}:\n{result.stderr.strip()}")
        return False
    return True


def gh_ready():
    return bool(shutil.which("gh")) and run(["gh", "auth", "status"]).returncode == 0


def get_owner():
    owner = run(["gh", "api", "user", "-q", ".login"]).stdout.strip()
    return owner if owner else None


def repo_exists(owner, name):
    return run(["gh", "repo", "view", f"{owner}/{name}"]).returncode == 0


def listar_repos_usuario(limit=50):
    """Lista los repos del usuario logueado. Devuelve lista de dicts."""
    result = run(["gh", "repo", "list", "--limit", str(limit), "--json", "name,isPrivate,updatedAt,url"])
    if result.returncode != 0:
        print("No pude listar los repos.")
        return []
    import json
    return json.loads(result.stdout)


def crear_repo_privado(nombre, owner):
    if repo_exists(owner, nombre):
        print(f"El repo '{nombre}' ya existe.")
        return True
    result = run(["gh", "repo", "create", nombre, "--private"])
    if not check(result, "crear el repo"):
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
    return input("Nombre del repo: ").strip().replace(" ", "-")


def confirm(question):
    while True:
        answer = input(f"{question} (s/n): ").strip().lower()
        if answer in ("s", "si", "sí"):
            return True
        if answer in ("n", "no"):
            return False
        print("Escribí 's' o 'n'.")


def guardar(vault, owner, name):
    url = f"https://github.com/{owner}/{name}.git"

    if not (vault / ".git").exists():
        if not check(run(["git", "init", "-b", "main"], cwd=vault), "git init"):
            return False
    gitignore = vault / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(".obsidian/workspace*.json\n", encoding="utf-8")

    has_origin = run(["git", "remote", "get-url", "origin"], cwd=vault).returncode == 0
    run(["git", "remote", "set-url" if has_origin else "add", "origin", url], cwd=vault)

    run(["git", "add", "-A"], cwd=vault)
    if run(["git", "diff", "--cached", "--quiet"], cwd=vault).returncode != 0:
        msg = f"auto: {datetime.now():%Y-%m-%d %H:%M}"
        if not check(run(["git", "commit", "-m", msg], cwd=vault), "git commit"):
            return False
    else:
        print("Sin cambios nuevos.")

    return check(run(["git", "push", "-u", "origin", "main"], cwd=vault), "git push")


def subir_notas():
    """Flujo completo: elegir carpeta → elegir/repo crear → commit + push."""
    vault = choose_path()
    if not vault:
        print("No elegiste ninguna carpeta.")
        return

    repos = listar_repos_usuario()
    if not repos:
        print("No tienes repos visibles. ¿Querés crear uno nuevo?")
        if confirm("Crear repo privado nuevo?"):
            name = ask_name()
            if not name:
                print("Falta el nombre del repo.")
                return
            owner = get_owner()
            if not owner:
                sys.exit("No pude obtener tu usuario de GitHub.")
            if crear_repo_privado(name, owner):
                print(f"Repo creado: https://github.com/{owner}/{name}")
                return guardar(vault, owner, name)
            else:
                return
        else:
            return

    print("\nTus repos:")
    for i, r in enumerate(repos, 1):
        private = "🔒" if r.get("isPrivate") else ""
        print(f"  {i}. {r['name']} {private} | actualizado {r.get('updatedAt', '?')}")

    print("\nOpción: elegir número o escribir nombre nuevo")
    eleccion = input("> ").strip()

    repos_elige = None
    try:
        idx = int(eleccion)
        if 1 <= idx <= len(repos):
            repos_elige = repos[idx - 1]
    except ValueError:
        pass

    if repos_elige is None:
        match = [r for r in repos if r.get("name", "").lower() == eleccion.lower()]
        if match:
            repos_elige = match[0]
        else:
            name = eleccion
            if not name:
                print("Falta el nombre del repo.")
                return
            owner = get_owner()
            if not owner:
                sys.exit("No pude obtener tu usuario de GitHub.")
            if crear_repo_privado(name, owner):
                repos_elige = {"name": name, "url": f"https://github.com/{owner}/{name}.git"}
                print(f"Repo creado: https://github.com/{owner}/{name}")
            else:
                return
            return guardar(vault, owner, repos_elige["name"])

    name = repos_elige["name"]
    repo_url = repos_elige.get("url", "")
    if repo_url:
        owner = repo_url.rstrip("/").replace(".git", "").split("/")[-2]
    else:
        owner = get_owner()
        if not owner:
            sys.exit("No pude obtener tu usuario de GitHub.")

    return guardar(vault, owner, name)


def traer_notas():
    """Listar repos, elegir uno y clonarlo para extraer notas."""
    repos = listar_repos_usuario()
    if not repos:
        print("No hay repos para traer notas.")
        return

    print("\nTus repos (con possible notas):")
    for i, r in enumerate(repos, 1):
        print(f"  {i}. {r['name']}")

    print("\nElegí el número del repo del que querés traer notas:")
    eleccion = input("> ").strip()
    try:
        idx = int(eleccion)
        if 1 <= idx <= len(repos):
            selected = repos[idx - 1]
        else:
            print("Número fuera de rango.")
            return
    except ValueError:
        print("Entrada inválida.")
        return

    owner = get_owner()
    repo_name = selected["name"]

    dest = Path.home() / "Notas" / f"{owner}_{repo_name}"

    print(f"Clonando {repo_name} → {dest} ...")
    result = run(["gh", "repo", "clone", f"{owner}/{repo_name}", str(dest)])
    if result.returncode != 0:
        print(f"Error al clonar: {result.stderr.strip()}")
        if dest.exists() and not any(dest.iterdir()):
            shutil.rmtree(dest)
        return

    print(f"Repo clonado en {dest}")
    print("Ahora podés copiar las notas que quieras de esa carpeta.")
    print("Ejemplo: las .md o la carpeta .obsidian dentro del repo clonado.")


def menu_principal():
    while True:
        print("\n=== Notas Unificadas ===")
        print("1. Subir notas")
        print("2. Traer notas")
        print("3. Salir")
        opcion = input("Elegí una opción (1-3): ").strip()

        if opcion == "1":
            subir_notas()
        elif opcion == "2":
            traer_notas()
        elif opcion == "3":
            print("Hasta luego!")
            break
        else:
            print("Opción inválida, intentá de nuevo.")


if __name__ == "__main__":
    if not shutil.which("git"):
        sys.exit("Falta instalar git.")
    if not gh_ready():
        sys.exit("Instalá GitHub CLI y corré 'gh auth login'.")
    menu_principal()