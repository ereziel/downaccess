"""
release.py — Bump version, build installeur Inno Setup, crée la release GitHub.

Usage :
    python scripts/release.py 0.1.3

Les release notes sont générées automatiquement depuis git log (commits
depuis le dernier tag). Aucune saisie requise.

Prérequis :
  - Build déjà fait (python scripts/build.py)
  - gh CLI installé et authentifié
  - Inno Setup 6 installé dans le chemin standard

Étapes :
  1. Vérifie que le build existe
  2. Génère les release notes depuis git log
  3. Bumpe la version dans app/version.py et installer/downaccess.iss
  4. Commit + push
  5. Lance Inno Setup → installer_output/DownAccess-Setup.exe
  6. Crée le tag git et la release GitHub avec l'installeur en pièce jointe
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
        print(f"  ERR Echec (code {r.returncode})")
        sys.exit(1)
    return r


def step(msg: str) -> None:
    print(f"\n>> {msg}")


def ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _generate_notes(tag: str) -> str:
    """Génère les release notes depuis git log (commits depuis le dernier tag)."""
    # Trouver le dernier tag existant
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0"],
        cwd=ROOT, capture_output=True, text=True,
    )
    last_tag = result.stdout.strip() if result.returncode == 0 else ""

    # Récupérer les commits depuis ce tag (ou tous si premier tag)
    ref = f"{last_tag}..HEAD" if last_tag else "HEAD"
    log = subprocess.run(
        ["git", "log", ref, "--pretty=format:- %s", "--no-merges"],
        cwd=ROOT, capture_output=True, text=True,
    )
    commits = log.stdout.strip()

    ffmpeg_ver = ""
    vf = ROOT / "assets" / "ffmpeg_version.txt"
    if vf.exists():
        for line in vf.read_text(encoding="utf-8").splitlines():
            if line.startswith("updated="):
                ffmpeg_ver = f"\nffmpeg : {line.split('=',1)[1]}"

    notes = f"## DownAccess {tag}\n\n"
    if commits:
        notes += "### Changements\n" + commits + "\n"
    else:
        notes += "- Mise à jour interne\n"
    if ffmpeg_ver:
        notes += f"\n### Dépendances{ffmpeg_ver}\n"
    return notes


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage : python scripts/release.py <version>")
        print("  Ex  : python scripts/release.py 0.1.3")
        return 1

    version = sys.argv[1].lstrip("v")
    tag     = f"v{version}"

    # 1. Vérifier le build
    step("Verification du build...")
    if not EXE.exists():
        print(f"  ERR Build introuvable : {EXE}")
        print("  -> Lance d'abord : python scripts/build.py")
        return 1
    ok(f"Build trouve : {EXE}")

    # 2. Générer les release notes
    step("Generation des release notes depuis git log...")
    notes = _generate_notes(tag)
    print(notes)
    ok("Release notes generees")

    # 3. Bumper version.py
    step(f"Bump version -> {version}...")
    content = VERSION_PY.read_text(encoding="utf-8")
    content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"', content)
    VERSION_PY.write_text(content, encoding="utf-8")
    ok(f"app/version.py -> {version}")

    content = ISS_FILE.read_text(encoding="utf-8")
    content = re.sub(r'AppVersion=[\d.]+', f'AppVersion={version}', content)
    ISS_FILE.write_text(content, encoding="utf-8")
    ok(f"installer/downaccess.iss -> {version}")

    # 4. Commit + push
    step("Commit et push...")
    run(["git", "add", str(VERSION_PY), str(ISS_FILE)], cwd=ROOT)
    run(["git", "commit", "-m", f"chore: version {version}"], cwd=ROOT)
    run(["git", "push"], cwd=ROOT)
    ok("Commit pousse")

    # 5. Inno Setup
    step("Build installeur Inno Setup...")
    if not ISCC.exists():
        print(f"  ERR ISCC introuvable : {ISCC}")
        print("  -> Installe Inno Setup 6 ou verifie le chemin dans ce script")
        return 1
    (ROOT / "installer_output").mkdir(exist_ok=True)
    run([str(ISCC), str(ISS_FILE)], cwd=ROOT)
    if not INSTALLER.exists():
        print(f"  ERR Installeur non genere : {INSTALLER}")
        return 1
    size_mb = INSTALLER.stat().st_size / 1_048_576
    ok(f"Installeur genere ({size_mb:.1f} Mo)")

    # 6. Release GitHub
    step(f"Creation de la release GitHub {tag}...")
    run([
        "gh", "release", "create", tag,
        str(INSTALLER),
        "--title", f"DownAccess {tag}",
        "--notes", notes,
    ], cwd=ROOT)
    ok(f"Release {tag} publiee sur GitHub")

    print(f"\nOK  Release {tag} terminee avec succes !")
    return 0


if __name__ == "__main__":
    sys.exit(main())
