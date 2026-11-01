import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    for carpeta in ("build", "dist"):
        shutil.rmtree(os.path.join(BASE, carpeta), ignore_errors=True)

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile",
        "--windowed",
        "--name", "Cropic",
        "--icon", os.path.join(BASE, "ui", "img", "cropic.ico"),
        "--add-data", f"{os.path.join(BASE, 'ui')}{os.pathsep}ui",
        "--add-data", f"{os.path.join(BASE, 'models')}{os.pathsep}models",
        "--hidden-import", "webview.platforms.edgechromium",
        "--hidden-import", "clr",
        "--collect-all", "webview",
        "--exclude-module", "PySide6",
        "--exclude-module", "PyQt5",
        "--exclude-module", "matplotlib",
        "--exclude-module", "tkinter",
        os.path.join(BASE, "app.py"),
    ]
    print(" ".join(cmd), "\n")
    r = subprocess.run(cmd, cwd=BASE)
    if r.returncode:
        sys.exit(r.returncode)

    exe = os.path.join(BASE, "dist", "Cropic.exe")
    if os.path.exists(exe):
        print(f"\nListo: {exe}  ({os.path.getsize(exe) / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
