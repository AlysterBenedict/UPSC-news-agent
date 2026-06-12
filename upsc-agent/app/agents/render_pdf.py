"""
UPSC Daily Digest — PDF Renderer Agent
========================================
Converts compiled HTML to A4 PDF using WeasyPrint.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from app.utils.logging import get_logger

log = get_logger(__name__)


def render_pdf(state: dict) -> dict:
    """
    PDF Renderer: Convert compiled HTML to A4 PDF.

    Uses WeasyPrint for CSS-based PDF rendering with proper
    pagination, page numbers, and professional typography.
    """
    compiled_html_path = state.get("compiled_html_path")
    run_id = state.get("run_id", "unknown")
    run_date = state.get("run_date", "")

    log.info("render_start", run_id=run_id, html_path=compiled_html_path)

    if not compiled_html_path or not Path(compiled_html_path).exists():
        log.error("html_not_found", path=compiled_html_path)
        return {
            "errors": [{
                "phase": "render",
                "error_type": "file_not_found",
                "message": f"Compiled HTML not found: {compiled_html_path}",
            }],
            "current_phase": "render_failed",
        }

    from config.settings import get_settings
    settings = get_settings()

    # Output path
    output_dir = settings.output_path
    pdf_filename = f"UPSC_Digest_{run_date}.pdf"
    pdf_path = output_dir / pdf_filename

    # Also save in run dir
    run_dir = settings.run_dir(run_id)
    run_pdf_path = run_dir / pdf_filename

    start_time = time.time()

    try:
        from weasyprint import HTML

        log.info("weasyprint_rendering", html_path=compiled_html_path)

        html_doc = HTML(filename=str(compiled_html_path))
        document = html_doc.render()

        # Get page count
        page_count = len(document.pages)

        # Write PDF to both locations
        document.write_pdf(str(pdf_path))
        document.write_pdf(str(run_pdf_path))

        render_time = time.time() - start_time

        log.info(
            "render_complete",
            run_id=run_id,
            pdf_path=str(pdf_path),
            pages=page_count,
            render_time=f"{render_time:.1f}s",
            file_size_mb=f"{pdf_path.stat().st_size / 1024 / 1024:.1f}",
        )

        return {
            "compiled_pdf_path": str(pdf_path),
            "current_phase": "rendered",
            "metrics": {
                "actual_pages": page_count,
                "render_time_seconds": render_time,
            },
        }

    except ImportError:
        log.warning("weasyprint_not_available, using fallback")
        return _fallback_render(compiled_html_path, pdf_path, run_pdf_path, run_id)
    except Exception as weasyprint_err:
        log.warning("weasyprint_render_failed_attempting_css_strip", error=str(weasyprint_err))
        
        try:
            # 1. Read the compiled HTML
            html_content = Path(compiled_html_path).read_text(encoding="utf-8")
            
            # 2. Strip complex styles and remote imports
            import re
            # Remove all <style>...</style> blocks
            html_content_clean = re.sub(r'<style\b[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
            # Remove remote stylesheets link tags
            html_content_clean = re.sub(r'<link[^>]*rel=["\']stylesheet["\'][^>]*>', '', html_content_clean, flags=re.IGNORECASE)
            
            # 3. Inject basic, guaranteed-to-work HTML print template CSS style
            basic_css = """
<style>
    @page {
        size: A4;
        margin: 20mm;
    }
    body {
        font-family: Georgia, serif;
        line-height: 1.5;
        color: #000;
        background: #fff;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: Arial, sans-serif;
        color: #111;
        margin-top: 1em;
        margin-bottom: 0.5em;
        page-break-after: avoid;
    }
    .brief-card {
        border-bottom: 1px solid #ccc;
        padding-bottom: 15px;
        margin-bottom: 15px;
        page-break-inside: avoid;
    }
    table {
        width: 100%;
        border-collapse: collapse;
        margin: 10px 0;
        page-break-inside: avoid;
    }
    th, td {
        border: 1px solid #ccc;
        padding: 6px 8px;
        text-align: left;
        font-size: 11pt;
    }
    ul, ol {
        margin-top: 5px;
        margin-bottom: 5px;
        padding-left: 20px;
    }
    .meta-row {
        font-size: 9pt;
        color: #555;
        margin-bottom: 10px;
    }
    .way-forward-box {
        border: 1px solid #ccc;
        background-color: #f9f9f9;
        padding: 8px;
        margin: 10px 0;
    }
</style>
"""
            if "</head>" in html_content_clean:
                html_content_clean = html_content_clean.replace("</head>", f"{basic_css}</head>")
            else:
                html_content_clean = basic_css + html_content_clean
            
            # Write this to a fallback HTML file
            fallback_html_path = Path(compiled_html_path).parent / "compiled_digest_fallback.html"
            fallback_html_path.write_text(html_content_clean, encoding="utf-8")
            
            log.info("retrying_weasyprint_with_cleaned_css", path=str(fallback_html_path))
            
            from weasyprint import HTML
            html_doc = HTML(filename=str(fallback_html_path))
            document = html_doc.render()
            
            page_count = len(document.pages)
            document.write_pdf(str(pdf_path))
            document.write_pdf(str(run_pdf_path))
            
            render_time = time.time() - start_time
            log.info("weasyprint_fallback_render_success_after_css_strip", pages=page_count, render_time=f"{render_time:.1f}s")
            
            return {
                "compiled_pdf_path": str(pdf_path),
                "current_phase": "rendered",
                "metrics": {
                    "actual_pages": page_count,
                    "render_time_seconds": render_time,
                },
            }
        except Exception as retry_err:
            log.error("weasyprint_retry_failed_using_html_fallback", error=str(retry_err))
            
            # Last resort: copy HTML directly as output, and inject an auto-print/open script
            import shutil
            import webbrowser
            html_output_path = pdf_path.with_suffix(".html")
            run_html_output_path = run_pdf_path.with_suffix(".html")
            
            # Injects a script to trigger print and show a warning
            html_content = Path(compiled_html_path).read_text(encoding="utf-8")
            script_inject = """
            <script>
                window.onload = function() {
                    alert("UPSC Daily Digest: PDF rendering failed. Showing the HTML version. Press OK to print/save as PDF from your browser.");
                    window.print();
                }
            </script>
            """
            # Inject right before </body>
            if "</body>" in html_content:
                html_content = html_content.replace("</body>", f"{script_inject}</body>")
            else:
                html_content += script_inject
                
            html_output_path.write_text(html_content, encoding="utf-8")
            shutil.copy2(str(html_output_path), str(run_html_output_path))
            
            log.info("html_resilience_fallback_saved", path=str(html_output_path))
            
            # Auto-open HTML file in user's browser
            try:
                webbrowser.open(html_output_path.as_uri())
            except Exception as web_err:
                log.warning("failed_to_auto_open_browser", error=str(web_err))
                
            return {
                "compiled_pdf_path": str(html_output_path),
                "current_phase": "rendered_html_only",
                "errors": [{
                    "phase": "render",
                    "error_type": "render_exception_fallback",
                    "message": f"WeasyPrint failed: {weasyprint_err}. Fallback retry failed: {retry_err}. Saved HTML version.",
                }],
                "metrics": {
                    "actual_pages": 0,
                    "render_time_seconds": time.time() - start_time,
                }
            }


def _fallback_render(html_path: str, pdf_path: Path, run_pdf_path: Path, run_id: str) -> dict:
    """Fallback PDF rendering using pdfkit/wkhtmltopdf if available."""
    try:
        import pdfkit
        pdfkit.from_file(str(html_path), str(pdf_path))
        pdfkit.from_file(str(html_path), str(run_pdf_path))

        log.info("fallback_render_complete", method="pdfkit", path=str(pdf_path))
        return {
            "compiled_pdf_path": str(pdf_path),
            "current_phase": "rendered",
            "metrics": {"actual_pages": 0, "render_time_seconds": 0},
        }
    except Exception as e:
        log.error("fallback_render_failed", error=str(e))
        # Last resort: save HTML as the output
        import shutil
        html_output = pdf_path.with_suffix(".html")
        shutil.copy2(html_path, str(html_output))
        return {
            "compiled_pdf_path": str(html_output),
            "current_phase": "rendered_html_only",
            "errors": [{
                "phase": "render",
                "error_type": "no_pdf_renderer",
                "message": f"Neither WeasyPrint nor pdfkit available. HTML saved: {html_output}",
            }],
        }
