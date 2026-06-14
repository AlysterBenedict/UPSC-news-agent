"""
UPSC News Agent — Standalone EXE Build Script
==============================================
Runs PyInstaller with correct arguments to package:
- Backend python script and WebView bridge (app_app.py)
- Web UI assets (ui/)
- News scraper (scraper_test.py)
- LangGraph pipeline (upsc-app/app using _app modules)
- GTK DLL binaries (cairo, pango, glib, gobject, etc.) from active conda env
- Main python libraries

FIX: Now references app_app.py as entrypoint.
FIX: Removed external config/ dependency (internalized to settings_app.py).
"""

import os
import sys
import subprocess
import shutil

def main():
    print("\n=============================================================")
    print("  UPSC News Agent — Starting Standalone Windows EXE Build")
    print("=============================================================\n")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(current_dir)
    
    # 1. Determine Conda Environment Prefix
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if not conda_prefix:
        conda_prefix = sys.prefix
    print(f"[*] Active Conda Prefix: {conda_prefix}")

    # 2. Locate and bundle GTK / Cairo / Pango DLL binaries for WeasyPrint
    dll_dir = os.path.join(conda_prefix, "Library", "bin")
    binary_args = []
    
    if os.path.exists(dll_dir):
        print(f"[*] GTK DLL directory located: {dll_dir}")
        binary_args.append(f'--add-binary={os.path.join(dll_dir, "*.dll")};.')
        print(f"[OK] Added Library/bin/*.dll search paths to compiler.")
    else:
        print("[WARN] Conda env Library/bin not found! Dynamic PDF rendering may rely on HTML fallbacks.")

    # 3. Assemble PyInstaller commands
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name=UPSC_Digest_Agent",
        f'--icon={os.path.join(current_dir, "icon.ico")}',
        # Bundle GUI Files
        f'--add-data={os.path.join(current_dir, "ui")};ui',
        # Bundle Scraper test script
        f'--add-data={os.path.join(parent_dir, "scraper_test.py")};.',
        # Bundle UPSC News Agent Packages (self-contained, no external config/)
        f'--add-data={os.path.join(current_dir, "app")};app',
        # Collect dynamic resources and subpackages
        "--collect-all=weasyprint",
        "--collect-all=langgraph",
        "--collect-all=langchain_core",
        "--collect-all=openai",
        "--collect-all=pydantic",
        "--collect-all=pydantic_settings",
        "--collect-all=sentence_transformers",
        "--collect-all=sklearn",
        "--collect-all=bs4",
        "--collect-all=feedparser",
        "--collect-all=playwright",
        "--collect-all=webview",
    ]

    # Append DLL binary arguments
    cmd.extend(binary_args)

    # Append main app entrypoint (renamed to app_app.py)
    cmd.append("app_app.py")

    # Clean previous build artifacts
    build_dir = os.path.join(current_dir, "build")
    dist_dir = os.path.join(current_dir, "dist")
    spec_file = os.path.join(current_dir, "UPSC_Digest_Agent.spec")

    print("[*] Cleaning up previous build artifacts...")
    for path in (build_dir, dist_dir):
        if os.path.exists(path):
            shutil.rmtree(path)
    if os.path.exists(spec_file):
        os.remove(spec_file)

    # 4. Trigger compiler
    print("\n[*] Invoking PyInstaller compilation...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, cwd=current_dir, check=True)
        if result.returncode == 0:
            print("\n=============================================================")
            print("  [SUCCESS] Standalone EXE compiled successfully!")
            print(f"  Location: {os.path.join(dist_dir, 'UPSC_Digest_Agent.exe')}")
            print("=============================================================\n")
        else:
            print(f"\n[ERROR] PyInstaller compilation failed with code {result.returncode}")
            sys.exit(result.returncode)
    except Exception as e:
        print(f"\n[ERROR] Build execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
