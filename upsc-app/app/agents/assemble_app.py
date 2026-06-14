"""
UPSC Daily Digest — Document Assembler Agent
==============================================
Compiles section fragments into a master HTML document
with cover page, TOC, and section dividers.
Auto-generates Quick Revision table and Prelims Reference.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import re

from app.agents.write_sections_app import SECTION_CONFIG
from app.utils.logging_app import get_logger
from app.utils.text_app import word_count, estimate_pages

log = get_logger(__name__)


def _renumber_articles(html: str) -> str:
    """Re-number <h3> article headings sequentially across combined batches.

    LLM batches each start numbering from 1, so combined output has
    1,2,3,1,2,3... This fixes it to 1,2,3,4,5,6...
    """
    counter = [0]  # mutable container for closure

    def _replace_number(match):
        counter[0] += 1
        # Preserve the anchor tag if present before <h3>
        prefix = match.group(1) or ""
        h3_attrs = match.group(2) or ""
        title_rest = match.group(3)
        return f"{prefix}<h3{h3_attrs}>{counter[0]}. {title_rest}"

    # Match optional anchor + <h3> + number prefix
    # Pattern: (optional <a id="..."></a>)<h3 ...>\d+\.\s*rest of title
    return re.sub(
        r'(<a\s+id="[^"]*"></a>)?\s*<h3([^>]*)>\s*\d+\.\s*(.*?)(?=</h3>|<)',
        _replace_number,
        html,
        flags=re.IGNORECASE,
    )


def _build_revision_table_html(verified_units: list[dict], unit_to_section: dict[str, str]) -> str:
    """Auto-generate a consolidated Revision Table from all verified units.

    Grouped by GS section (e.g., GS2: Polity & Governance).
    Simple cheat-sheet format with 3 columns:
    1. Title (linked to detailed section)
    2. Key Data Points (2-3 most critical numbers/facts)
    3. What Happened (one-line summary)
    """
    if not verified_units:
        return ""

    # Group units by their routed section
    from collections import defaultdict
    section_units: dict[str, list[dict]] = defaultdict(list)

    for unit in verified_units:
        unit_id = unit.get("unit_id", "")
        section_key = unit_to_section.get(unit_id, "other")
        section_units[section_key].append(unit)

    # Order sections using SECTION_CONFIG
    ordered_section_keys = sorted(
        section_units.keys(),
        key=lambda s: SECTION_CONFIG.get(s, {}).get("order", 99),
    )

    rows = []
    for section_key in ordered_section_keys:
        units = section_units[section_key]
        config = SECTION_CONFIG.get(section_key, {})
        display_name = config.get("display_name", section_key.replace("_", " ").title())

        # Section sub-header row
        rows.append(
            f'<tr class="revision-section-header">'
            f'<td colspan="3"><strong>{display_name}</strong></td>'
            f'</tr>'
        )

        # Sort units within section by relevance score (highest first)
        for unit in sorted(units, key=lambda u: u.get("upsc_relevance_score", 0), reverse=True):
            topic = unit.get("title", "")
            unit_id = unit.get("unit_id", "")
            # Link directly to the per-article anchor (injected in write_sections)
            topic_html = f'<a href="#{unit_id}">{topic}</a>' if unit_id else topic

            # Key data points from the dedicated revision field
            key_data = unit.get("revision_key_data_points", [])
            if not key_data:
                # Fallback: use first 2 data_points if revision field is empty
                key_data = unit.get("data_points", [])[:2]

            if key_data:
                data_html = "<ul>" + "".join(
                    f"<li>{dp.strip()}</li>" for dp in key_data if dp.strip()
                ) + "</ul>"
            else:
                data_html = "—"

            # One-line summary from the dedicated revision field
            summary = unit.get("revision_one_line_summary", "")
            if not summary:
                # Fallback: use first factual_summary item
                facts = unit.get("factual_summary", [])
                summary = facts[0].strip() if facts else "—"

            tr_id = f' id="rev_{unit_id}"' if unit_id else ""
            rows.append(f"<tr{tr_id}><td>{topic_html}</td><td>{data_html}</td><td>{summary}</td></tr>")

    return f"""<table>
<thead><tr><th>Topic</th><th>Key Data Points</th><th>What Happened</th></tr></thead>
<tbody>{"".join(rows)}</tbody>
</table>"""


def assemble_document(state: dict) -> dict:
    """
    Document Assembler: Compile all sections into master HTML.

    Builds the complete digest document with cover, TOC, and all sections.
    Auto-generates a consolidated Revision Table from verified units.
    """
    section_fragments = state.get("section_fragments", {})
    verified_units = state.get("verified_units", [])
    run_id = state.get("run_id", "unknown")
    run_date = state.get("run_date", "")

    log.info("assembly_start", run_id=run_id, sections=len(section_fragments))

    # Compute statistics
    total_articles = len(state.get("articles_raw", []))
    total_clusters = len(state.get("article_clusters", []))
    total_verified = len(verified_units)
    sources = list(set(
        a.get("source", a.get("source_name", ""))
        for a in state.get("articles_normalized", state.get("articles_raw", []))
    ))

    # Extract key themes from high-relevance units
    themes = []
    for unit in sorted(verified_units, key=lambda u: u.get("upsc_relevance_score", 0), reverse=True)[:8]:
        themes.append(unit.get("title", ""))

    # Build a mapping from unit_id to section name
    unit_to_section = {}
    for sec_name, buffer_items in state.get("section_buffers", {}).items():
        if isinstance(buffer_items, list):
            for item in buffer_items:
                if isinstance(item, dict) and "unit_id" in item:
                    unit_to_section[item["unit_id"]] = sec_name

    # Order sections
    ordered_sections = sorted(
        section_fragments.keys(),
        key=lambda s: SECTION_CONFIG.get(s, {}).get("order", 99),
    )

    # Build TOC and section content
    toc_entries = []
    sections_html = []
    total_words_count = 0

    # 1. Auto-generate consolidated Revision Table
    revision_html = _build_revision_table_html(verified_units, unit_to_section)
    if revision_html:
        revision_wc = word_count(revision_html)
        total_words_count += revision_wc
        toc_entries.append({
            "name": "Revision Table",
            "anchor": "revision_table",
            "word_count": revision_wc,
        })
        sections_html.append({
            "name": "Revision Table",
            "anchor": "revision_table",
            "content": revision_html,
            "word_count": revision_wc,
        })

    # 2. Detailed Brief Cards (ordered sections)
    for section_name in ordered_sections:
        fragments = section_fragments.get(section_name, [])
        if not fragments:
            continue

        config = SECTION_CONFIG.get(section_name, {})
        display_name = config.get("display_name", section_name)

        # Combine fragments and fix numbering across batches
        combined = "\n".join(fragments)
        combined = _renumber_articles(combined)
        wc = word_count(combined)
        total_words_count += wc

        toc_entries.append({
            "name": display_name,
            "anchor": section_name,
            "word_count": wc,
        })

        sections_html.append({
            "name": display_name,
            "anchor": section_name,
            "content": combined,
            "word_count": wc,
        })

    est_pages = estimate_pages(total_words_count)

    # Load Jinja2 templates
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )

    # Render the complete document
    try:
        template = env.get_template("base_app.html")
        compiled_html = template.render(
            run_date=run_date,
            formatted_date=datetime.strptime(run_date, "%Y-%m-%d").strftime("%d %B %Y") if run_date else "",
            run_id=run_id,
            total_articles=total_articles,
            total_clusters=total_clusters,
            total_verified=total_verified,
            sources=sources,
            themes=themes,
            toc_entries=toc_entries,
            sections=sections_html,
            total_words=total_words_count,
            generated_at=datetime.now().strftime("%d %B %Y, %I:%M %p IST"),
        )
    except Exception as e:
        log.error("template_render_error", error=str(e))
        # Fallback: raw HTML assembly
        compiled_html = _fallback_assemble(
            run_date, themes, toc_entries, sections_html,
            total_articles, total_verified, sources, total_words_count
        )

    # Final pass: validate and auto-correct HTML markup using BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(compiled_html, "html.parser")
        compiled_html = str(soup)
    except Exception as e:
        log.warning("assembled_html_validation_failed", error=str(e))

    # Save compiled HTML
    from app.services.settings_app import get_settings
    settings = get_settings()
    output_dir = settings.run_dir(run_id)
    html_path = output_dir / "compiled_digest.html"
    html_path.write_text(compiled_html, encoding="utf-8")

    log.info(
        "assembly_complete",
        run_id=run_id,
        total_words=total_words_count,
        estimated_pages=est_pages,
        sections=len(sections_html),
        html_path=str(html_path),
    )

    return {
        "compiled_html_path": str(html_path),
        "current_phase": "assembled",
        "metrics": {
            "total_words": total_words_count,
            "estimated_pages": est_pages,
            "sections_written": len(sections_html),
        },
    }


def _fallback_assemble(
    run_date, themes, toc_entries, sections_html,
    total_articles, total_verified, sources, total_words
):
    """Fallback HTML assembly without Jinja2 templates."""
    themes_html = "".join(f"<li>{t}</li>" for t in themes)
    toc_html = "".join(
        f'<li><a href="#{e["anchor"]}">{e["name"]}</a></li>'
        for e in toc_entries
    )
    sections_content = ""
    for s in sections_html:
        sections_content += f"""
        <section id="{s['anchor']}" class="digest-section">
            <h2 class="section-title">{s['name']}</h2>
            {s['content']}
        </section>
        """
    sources_html = ", ".join(sources[:15])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>UPSC Daily Digest — {run_date}</title>
    <style>
        @page {{ size: A4; margin: 1.5cm 1.5cm 2cm 1.5cm; @bottom-center {{ content: "Page " counter(page) " of " counter(pages); font-size: 8pt; color: #888; }} @bottom-right {{ content: element(back-to-rev); }} }}
        body {{ font-family: 'Helvetica Neue', 'Arial', sans-serif; font-size: 9.5pt; line-height: 1.4; color: #1a1a1a; }}
        h1 {{ color: #1a237e; }} h2 {{ color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 4px; }}
        h3 {{ color: #283593; font-size: 11pt; margin: 10px 0 4px 0; }} h4 {{ color: #3949ab; }}
        .cover {{ text-align: center; page-break-after: always; padding-top: 15%; }}
        .page-break {{ page-break-after: always; }}
        .digest-section {{ page-break-before: always; }}
        .brief-card {{ position: relative; border: 1px solid #e2e8f0; padding: 12px; margin-bottom: 15px; border-radius: 6px; }}
        .back-to-rev-container {{ position: running(back-to-rev); text-align: right; }}
        .back-to-revision-btn {{ font-size: 7.5pt; color: #1a237e; text-decoration: none; background: #f0f2f8; padding: 2px 6px; border-radius: 4px; border: 1px solid #d0d4e8; font-weight: 600; display: inline-block; }}
        .gs-tag {{ font-size: 8.5pt; color: #555; margin-top: 2px; padding: 4px 8px; background: #f5f5f5; border-left: 3px solid #1a237e; margin-right: 100px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 8px 0; font-size: 9pt; }}
        th, td {{ border: 1px solid #ccc; padding: 4px 8px; text-align: left; }}
        th {{ background: #1a237e; color: white; font-weight: 600; font-size: 8.5pt; }}
        tr:nth-child(even) {{ background: #f5f5f5; }}
        .source-appendix {{ page-break-before: always; font-size: 9pt; color: #555; }}
    </style>
</head>
<body>
    <div class="cover">
        <h1>UPSC Daily Newspaper Digest</h1>
        <p style="font-size: 18pt; color: #455a64;">{run_date}</p>
        <p style="font-size: 11pt; color: #666;">Articles Analyzed: {total_articles} | Unique Stories: {total_verified}</p>
        <p style="font-size: 9pt; color: #888;">Sources: {sources_html}</p>
        <div style="margin-top: 30px;">
            <h3 style="color: #37474f;">Key Themes Today</h3>
            <ul style="list-style: none; padding: 0; text-align: left; max-width: 500px; margin: 0 auto;">{themes_html}</ul>
        </div>
    </div>
    <h2>Table of Contents</h2>
    <ol>{toc_html}</ol>
    <div class="page-break"></div>
    {sections_content}
    <section class="source-appendix">
        <h2>Source References</h2>
        <p>This digest was generated from {total_articles} articles across: {sources_html}.</p>
        <p>Total words: {total_words:,}. Generated automatically by UPSC Daily Digest AI.</p>
    </section>
</body>
</html>"""
