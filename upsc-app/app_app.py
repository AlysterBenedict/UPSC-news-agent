"""
UPSC Digest News Agent — Desktop App Backend (PyWebView)
=========================================================
Standalone Python runner that boots the Webview UI, persists
the NVIDIA NIM API key in config.json, captures pipeline stdout/stderr,
and runs the multi-agent pipeline programmatically in a background thread.

FIX NOTES:
 - Settings internalized via app.services.settings_app (no external config/)
 - API key set into os.environ BEFORE any Settings() instantiation
 - LogEmitter uses batched dispatch with proper timing
 - All imports use _app suffixed modules
"""

from __future__ import annotations

import os
import sys
import json
import shutil
import queue
import threading
import subprocess
import time
from pathlib import Path

# --- RESOLVE PATHS FOR IMPORTS & ENVIRONMENT ---
if getattr(sys, 'frozen', False):
    # PyInstaller temporary extraction folder
    bundle_dir = sys._MEIPASS
    app_dir = os.path.dirname(sys.executable)
else:
    # Development mode directory
    bundle_dir = os.path.dirname(os.path.abspath(__file__))
    app_dir = bundle_dir

# Add project search directories to python sys.path
sys.path.insert(0, bundle_dir)
parent_dir = os.path.dirname(bundle_dir)
if not getattr(sys, 'frozen', False):
    # Add parent directory in development mode so that scraper_test.py is resolvable
    sys.path.insert(0, parent_dir)

# --- SUBPROCESS INTERCEPTION PATTERN ---
# If this file is called with scraper_test.py as the first argument,
# it means the pipeline is trying to run the scraper as a subprocess.
# We intercept the execution and run the scraper directly in-process!
if len(sys.argv) > 1 and "scraper_test.py" in sys.argv[1]:
    try:
        # Remove the script path from sys.argv so argparse parses options correctly
        sys.argv.pop(1)
        
        # Import and run scraper_test
        import scraper_test
        import argparse
        from datetime import datetime, timezone, timedelta
        
        ap = argparse.ArgumentParser()
        ap.add_argument("--tier", type=int, default=3)
        ap.add_argument("--delay", type=float, default=1.5)
        ap.add_argument("--sources", nargs="+", default=None)
        ap.add_argument("--date", type=str, default=None)
        args = ap.parse_args()
        
        if args.date:
            date_str = args.date.strip().lower()
            if date_str == "yesterday":
                target_dt = datetime.now(scraper_test.IST) - timedelta(days=1)
            elif date_str == "today":
                target_dt = datetime.now(scraper_test.IST)
            else:
                try:
                    target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=scraper_test.IST)
                except ValueError:
                    print(f"Error: Invalid date format '{args.date}'.")
                    sys.exit(1)
            scraper_test.TODAY_DT = target_dt
            scraper_test.TODAY_STR = target_dt.strftime("%Y-%m-%d")
            
        articles, stats = scraper_test.run_scraper(
            tier_limit=args.tier,
            delay=args.delay,
            source_filter=args.sources
        )
        json_path, report_path, report_text = scraper_test.save_outputs(articles, stats)
        print(report_text)
        sys.exit(0)
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)

import webview

# Global configuration filepath
CONFIG_PATH = os.path.join(app_dir, "config.json")

def check_and_install():
    """Checks if running from the installed path; if not, installs and registers in Start Menu."""
    if not getattr(sys, 'frozen', False):
        return

    # Do not install if executing as a scraper subprocess
    if len(sys.argv) > 1 and "scraper_test.py" in sys.argv[1]:
        return

    target_dir = os.path.join(os.environ["LOCALAPPDATA"], "Programs", "UPSC_Digest_Agent")
    target_exe = os.path.join(target_dir, "UPSC_Digest_Agent.exe")
    current_exe = sys.executable

    if os.path.normpath(current_exe).lower() != os.path.normpath(target_exe).lower():
        try:
            os.makedirs(target_dir, exist_ok=True)
            
            # Copy executable to local programs directory
            shutil.copy2(current_exe, target_exe)
            
            # Register in Windows Start Menu using PowerShell script
            lnk_path = os.path.join(
                os.environ["APPDATA"], 
                "Microsoft", "Windows", "Start Menu", "Programs", 
                "UPSC Digest Agent.lnk"
            )
            
            ps_script = f"""
            $s = (New-Object -ComObject WScript.Shell).CreateShortcut("{lnk_path}");
            $s.TargetPath = "{target_exe}";
            $s.IconLocation = "{target_exe}";
            $s.WorkingDirectory = "{target_dir}";
            $s.Save();
            """
            
            subprocess.run(["powershell", "-Command", ps_script], capture_output=True)
            
            # Boot the installed executable and close this one
            subprocess.Popen([target_exe])
            sys.exit(0)
        except Exception as e:
            print(f"[INSTALL ERROR] Failed self-installation sequence: {e}")


# --- STDOUT/STDERR LOG REDIRECTOR ---
class LogEmitter:
    """Redirects stdout and stderr streams to the webview console in real-time.
    
    FIX: Uses time-based batching with a minimum interval (100ms) to prevent
    flooding evaluate_js with hundreds of rapid log lines. Also protects
    against window being destroyed mid-dispatch.
    """
    def __init__(self, window):
        self.window = window
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.queue = queue.Queue()
        self.running = True
        self._MIN_DISPATCH_INTERVAL = 0.1  # 100ms batching window
        
        # Spawn a thread to dispatch logs to prevent blocking the outputting process
        self.dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self.dispatch_thread.start()

    def write(self, text):
        if self.original_stdout:
            self.original_stdout.write(text)
            self.original_stdout.flush()
        if text and text.strip():  # FIX: skip empty/whitespace-only writes
            self.queue.put(text)

    def flush(self):
        if self.original_stdout:
            self.original_stdout.flush()

    def isatty(self):
        return False

    def _dispatch_loop(self):
        buffer = []
        
        while self.running:
            try:
                line = self.queue.get(timeout=self._MIN_DISPATCH_INTERVAL)
                buffer.append(line)
            except queue.Empty:
                pass
            
            # Drain everything currently in queue
            while not self.queue.empty():
                try:
                    buffer.append(self.queue.get_nowait())
                except queue.Empty:
                    break
            
            if buffer:
                log_chunk = "".join(buffer)
                buffer.clear()
                try:
                    js_escaped = json.dumps(log_chunk)
                    self.window.evaluate_js(f"if(window.onLog) {{ window.onLog({js_escaped}); }}")
                except Exception:
                    # Window may have been destroyed
                    pass
        
        # Final flush
        while not self.queue.empty():
            try:
                text = self.queue.get_nowait()
                if self.original_stdout:
                    self.original_stdout.write(text)
            except queue.Empty:
                break

    def stop(self):
        self.running = False
        sys.stdout = self.original_stdout
        sys.stderr = self.original_stderr


# --- JAVASCRIPT API BRIDGE ---
class ApiBridge:
    def __init__(self):
        self.window = None

    def get_api_key(self) -> dict:
        """Load API Key from config.json."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return {"success": True, "api_key": data.get("nim_api_key", "")}
            return {"success": True, "api_key": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_api_key(self, api_key: str) -> dict:
        """Save API Key to config.json."""
        try:
            data = {}
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        pass
            data["nim_api_key"] = api_key
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_api_key(self) -> dict:
        """Delete API Key config."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = {}
                data["nim_api_key"] = ""
                with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=4)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def select_save_path(self, date_str: str) -> dict:
        """Open native save file dialog to choose output location."""
        try:
            filename = f"UPSC_Digest_{date_str}.pdf"
            file_types = ('PDF Files (*.pdf)', 'All Files (*.*)')
            
            result = self.window.create_file_dialog(
                webview.SAVE_DIALOG, 
                file_types=file_types, 
                save_filename=filename
            )
            
            if result:
                # If result is a list/tuple on some platforms, grab the first element
                save_path = result[0] if isinstance(result, (list, tuple)) else result
                return {"success": True, "save_path": save_path}
            return {"success": False, "error": "Save path not selected"}
        except Exception as e:
            print(f"[ERROR] file dialog failed: {e}")
            return {"success": False, "error": str(e)}

    def run_pipeline(self, date_str: str, save_path: str):
        """Run workflow in background thread."""
        t = threading.Thread(target=self._execute_workflow, args=(date_str, save_path), daemon=True)
        t.start()

    def open_file(self, file_path: str):
        """Open generated PDF file using system default program."""
        try:
            if os.path.exists(file_path):
                os.startfile(file_path)
        except Exception as e:
            print(f"[ERROR] Failed to open file: {e}")

    def open_folder(self, file_path: str):
        """Open file folder in Explorer and select the file."""
        try:
            if os.path.exists(file_path):
                # Highlight/select file in explorer
                subprocess.Popen(f'explorer /select,"{os.path.normpath(file_path)}"')
        except Exception as e:
            # Fallback to opening directory
            try:
                os.startfile(os.path.dirname(file_path))
            except Exception:
                print(f"[ERROR] Failed to open folder: {e}")

    def _execute_workflow(self, date_str: str, save_path: str):
        """Internal worker method to run LangGraph pipeline.
        
        FIX: Sets os.environ BEFORE any import that triggers Settings().
        FIX: Resets settings singleton so it reads fresh env vars.
        FIX: Uses _app suffixed imports throughout.
        """
        try:
            # 1. Fetch saved API key from local config
            config_res = self.get_api_key()
            api_key = config_res.get("api_key", "")
            if not api_key:
                self.window.evaluate_js(
                    "window.onPipelineComplete(false, 'NVIDIA NIM API key is not configured. Go to settings.')"
                )
                return

            # 2. Setup environment variables BEFORE any Settings() instantiation
            output_dir = os.path.join(app_dir, "output")
            data_dir = os.path.join(app_dir, "data")
            db_path = os.path.join(data_dir, "checkpoints.db")
            
            os.makedirs(output_dir, exist_ok=True)
            os.makedirs(data_dir, exist_ok=True)
            
            os.environ["NIM_API_KEY"] = api_key
            if getattr(sys, 'frozen', False):
                scraper_output_dir = os.path.join(app_dir, "zartifacts")
            else:
                scraper_output_dir = os.path.join(os.path.dirname(app_dir), "zartifacts")
            os.environ["SCRAPER_OUTPUT_DIR"] = scraper_output_dir
            os.environ["OUTPUT_DIR"] = output_dir
            os.environ["DATA_DIR"] = data_dir
            os.environ["DB_PATH"] = db_path

            print(f"\n[SYSTEM] Initializing multi-agent pipeline for date: {date_str}")
            print(f"[SYSTEM] Configured NIM_API_KEY dynamically")
            print(f"[SYSTEM] App Working Dir: {app_dir}")

            # 3. Reset settings singleton so it picks up fresh env vars
            from app.services.settings_app import reset_settings
            reset_settings()

            # 4. Import and configure pipeline logging
            from app.utils.logging_app import setup_logging
            setup_logging()
            
            # 5. Import pipeline modules (imported here to read overridden environment variables)
            from app.graph.workflow_app import run_workflow
            
            # 6. Execute Workflow
            final_state = run_workflow(
                run_date=date_str,
                scraper_output_dir=scraper_output_dir,
                checkpoint_db_path=db_path,
                skip_delivery=True,  # GUI App compiles local files only
                skip_scrape=False,   # Auto scraper run
            )

            # 7. Handle output
            pdf_output = final_state.get("compiled_pdf_path")
            
            if pdf_output and os.path.exists(pdf_output):
                # Copy file to user's desired location
                shutil.copy2(pdf_output, save_path)
                self.window.evaluate_js(f"window.onPipelineComplete(true, {json.dumps(save_path)})")
            else:
                # Handle WeasyPrint fallback to HTML output
                html_output = pdf_output.replace(".pdf", ".html") if pdf_output else None
                if html_output and os.path.exists(html_output):
                    user_html_path = save_path.replace(".pdf", ".html")
                    shutil.copy2(html_output, user_html_path)
                    self.window.evaluate_js(f"window.onPipelineComplete(true, {json.dumps(user_html_path)})")
                else:
                    # Try to find compiled_html_path directly
                    html_direct = final_state.get("compiled_html_path")
                    if html_direct and os.path.exists(html_direct):
                        user_html_path = save_path.replace(".pdf", ".html")
                        shutil.copy2(html_direct, user_html_path)
                        self.window.evaluate_js(f"window.onPipelineComplete(true, {json.dumps(user_html_path)})")
                    else:
                        self.window.evaluate_js(
                            "window.onPipelineComplete(false, 'Workflow finished but failed to output compiled PDF/HTML files.')"
                        )
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.window.evaluate_js(f"window.onPipelineComplete(false, {json.dumps(str(e))})")


# --- APP BOOTSTRAP ---
def main():
    check_and_install()
    api = ApiBridge()
    
    # Path to index.html (use _app renamed UI files)
    ui_html = os.path.join(bundle_dir, "ui", "index_app.html")
    # Fallback to original if renamed version not found
    if not os.path.exists(ui_html):
        ui_html = os.path.join(bundle_dir, "ui", "index.html")
    # WebView URL scheme for file access
    ui_url = 'file:///' + os.path.abspath(ui_html).replace('\\', '/')
    
    # Create webview window
    window = webview.create_window(
        title='UPSC Digest News Agent',
        url=ui_url,
        js_api=api,
        width=1080,
        height=720,
        min_size=(800, 550),
        background_color='#06070c'
    )
    
    api.window = window
    log_redirector = None

    # Redirect logs once window starts
    def on_window_loaded():
        nonlocal log_redirector
        log_redirector = LogEmitter(window)
        sys.stdout = log_redirector
        sys.stderr = log_redirector

    window.events.loaded += on_window_loaded

    # Start PyWebView
    # gui='mshtml' is fallback, default on Windows is Webview2 (Chromium Edge)
    webview.start()

    # Clean up redirector when window closes
    if log_redirector:
        log_redirector.stop()

if __name__ == '__main__':
    main()
