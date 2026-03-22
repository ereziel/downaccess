"""
release.py — Bump version, build installeur Inno Setup, crée la release GitHub.

Usage :
    python scripts/release.py 0.1.3 "Notes de version"

Prérequis :
  - Build déjà fait (python scripts/build.py)
  - gh CLI installé et authentifié
  - Inno Setup 6 installé dans le chemin standard

Étapes :
  1. Vérifie que le build existe
  2. Bumpe la version dans app/version.py et installer/downaccess.iss
  3. Commit + push
  4. Lance Inno Setup → installer_output/DownAccess-Setup.exe
  5. Crée le tag git et la release GitHub avec l'installeur en pièce jointe
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT         = Path(__file__).parent.parent
EXE          = ROOT / "dist" / "DownAccess" / "DownAccess.exe"
VERSION_PY   = ROOT / "app" / "version.py"
ISS_FILE     = ROOT / "installer" / "downaccess.iss"
INSTALLER    = ROOT / "installer_output" / "DownAccess-Setup.exe"
ISCC         = Path(r"C:\Users\mathi\AppData\Local\Programs\Inno Setup 6\ISCC.exe")


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run(cmd, **kw)
    if r.returncode != 0:
        print(f"  ❌ Échec (code {r.returncode})")
        sys.exit(1)
    return r


def step(msg: str) -> None:
    print(f"\n>> {msg}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage : python scripts/release.py <version> [notes]")
        print("  Ex  : python scripts/release.py 0.1.3 'Correctifs divers'")
        return 1

    version = sys.argv[1].lstrip("v")
    notes   = sys.argv[2] if len(sys.argv) > 2 else f"DownAccess v{version}"
    tag     = f"v{version}"

    # 1. Vérifier le build
    step("Vérification du build…")
    if not EXE.exists():
        print(f"  ❌ Build introuvable : {EXE}")
        print("  → Lance d'abord : python scripts/build.py")
        return 1
    ok(f"Build trouvé : {EXE}")

    # 2. Bumper version.py
    step(f"Bump version → {version}…")
    content = VERSION_PY.read_text(encoding="utf-8")
    content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', content)
    VERSION_PY.write_text(content, encoding="utf-8")
    ok(f"app/version.py → {version}")

    # Bumper downaccess.iss
    content = ISS_FILE.read_text(encoding="utf-8")
    content = re.sub(r'AppVersion=[\d.]+', f'AppVersion={version}', content)
    ISS_FILE.write_text(content, encoding="utf-8")
    ok(f"installer/downaccess.iss → {version}")

    # 3. Commit + push
    step("Commit et push…")
    run(["git", "add", str(VERSION_PY), str(ISS_FILE)], cwd=ROOT)
    run(["git", "commit", "-m", f"chore: version {version}"], cwd=ROOT)
    run(["git", "push"], cwd=ROOT)
    ok("Commit poussé")

    # 4. Inno Setup
    step("Build installeur Inno Setup…")
    if not ISCC.exists():
        print(f"  ❌ ISCC introuvable : {ISCC}")
        print("  → Installe Inno Setup 6 ou vérifie le chemin dans ce script")
        return 1
    (ROOT / "installer_output").mkdir(exist_ok=True)
    run([str(ISCC), str(ISS_FILE)], cwd=ROOT)
    if not INSTALLER.exists():
        print(f"  ❌ Installeur non généré : {INSTALLER}")
        return 1
    size_mb = INSTALLER.stat().st_size / 1_048_576
    ok(f"Installeur généré ({size_mb:.1f} Mo) : {INSTALLER}")

    # 5. Release GitHub
    step(f"Création de la release GitHub {tag}…")
    run([
        "gh", "release", "create", tag,
        str(INSTALLER),
        "--title", f"DownAccess {tag}",
        "--notes", notes,
    ], cwd=ROOT)
    ok(f"Release {tag} publiée sur GitHub")

    print(f"\n✅ Release {tag} terminée avec succès !")
    return 0


if __name__ == "__main__":
    sys.exit(main())
