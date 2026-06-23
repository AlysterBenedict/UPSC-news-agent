"""
UPSC Daily Digest — Section Writer Agent
==========================================
Writes one section at a time from verified units.
Uses compact numbered-brief format for UPSC digest.

STRICT RULES ENFORCED:
  - Source-faithful: no speculation, no added facts
  - Neutral tone: no editorializing, no hype words
  - Structured: What happened → Why it matters → Key data → GS tag
  - Compact: hard word caps per content depth
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.models.schemas_app import SectionName, ContentDepth
from app.utils.logging_app import get_logger

log = get_logger(__name__)

# Section display names and order
SECTION_CONFIG = {
    SectionName.GS2_POLITY.value: {
        "display_name": "GS2: Polity & Governance",
        "order": 1,
        "description": "Constitutional developments, governance reforms, judiciary rulings, welfare schemes, federal issues, internal security, civil services, parliamentary proceedings",
    },
    SectionName.GS2_IR.value: {
        "display_name": "GS2: International Relations",
        "order": 2,
        "description": "Bilateral and multilateral relations, strategic partnerships, international treaties, summits, India's foreign policy, global governance, UN and multilateral bodies",
    },
    SectionName.GS3_ECONOMY.value: {
        "display_name": "GS3: Economy",
        "order": 3,
        "description": "Macroeconomy, monetary policy, trade, infrastructure, fiscal policy, agriculture, industry, employment, financial markets, banking and insurance",
    },
    SectionName.GS3_ENVIRONMENT.value: {
        "display_name": "GS3: Environment & Ecology",
        "order": 4,
        "description": "Climate change, biodiversity, conservation, environmental regulation, pollution, renewable energy, wildlife, disaster management",
    },
    SectionName.GS3_SCITECH.value: {
        "display_name": "GS3: Science & Technology",
        "order": 5,
        "description": "Space, biotech, digital governance, defence technology, AI, health science, nuclear, semiconductors, cybersecurity",
    },
    SectionName.GS1_SOCIETY.value: {
        "display_name": "GS1: Society & Geography",
        "order": 6,
        "description": "Social issues, gender, caste, migration, vulnerable groups, education, demography, urbanization, geography, cultural heritage",
    },
    SectionName.EDITORIAL.value: {
        "display_name": "Editorial & Explained Analysis",
        "order": 8,
        "description": "Deep editorial analysis with argument, context, counterview, UPSC framing",
    },
    SectionName.PIB.value: {
        "display_name": "PIB",
        "order": 7,
        "description": "Press Information Bureau releases, government updates, and official briefings",
    },
}


# =============================================================================
# PRODUCTION-GRADE WRITER PROMPTS
# =============================================================================

SECTION_WRITER_SYSTEM_PROMPT = """You are a UPSC Current Affairs Writer producing a structured, visual, exam-focused daily news digest. You write for serious UPSC aspirants — every word must serve their preparation.

YOUR OUTPUT FORMAT — for each article, produce EXACTLY this HTML structure:

<div class="brief-card">
  <h3>1. Article Title</h3>
  
  <div class="meta-row">
    <span class="source-tag">Sources: [Comma-separated list of sources, e.g., Indian Express, The Hindu]</span> | 
    <span class="syllabus-tag">Syllabus: [Comma-separated list of syllabus codes, e.g., GS2.1, GS3.5]</span> |
    <span class="static-tag">Static Sync: [Comma-separated list of connected static/theory topics from raw unit's static_links field, or N/A]</span>
  </div>

  <p class="summary"><strong>Summary:</strong> What happened. Why it matters for UPSC. Key data, numbers, institutions, Acts, or schemes involved. If a decision/policy was taken: the problem it addresses → what was decided → expected impact. Maximum {word_cap} words. Include inline source attributions where relevant (e.g., "...according to reports in [The Hindu]...").</p>

  <!-- Include this block only if at least one prelims metadata field is not "N/A" -->
  <div class="prelims-metadata-card">
    <table>
      <tr><td class="lbl">Nodal Ministry/Agency</td><td>[Nodal Ministry or N/A]</td></tr>
      <tr><td class="lbl">Constitutional/Statutory Status</td><td>[Constitutional/Statutory Status or N/A]</td></tr>
      <tr><td class="lbl">Key Articles/Amendments/Acts</td><td>[Relevant Articles/Acts or N/A]</td></tr>
      <tr><td class="lbl">IUCN/Conservation Status</td><td>[IUCN status, WPA schedule, or N/A]</td></tr>
    </table>
  </div>

  <!-- Include this table only if mains arguments favor or challenges concerns exist in the unit data -->
  <table class="mains-split-table">
    <tr>
      <td class="mains-col-pros">
        <strong>Arguments / Pros:</strong>
        <ul>
          <li>Bullet 1...</li>
          <li>Bullet 2...</li>
        </ul>
      </td>
      <td class="mains-col-cons">
        <strong>Concerns / Challenges:</strong>
        <ul>
          <li>Bullet 1...</li>
          <li>Bullet 2...</li>
        </ul>
      </td>
    </tr>
  </table>

  <!-- Include this box only if a Way Forward is mentioned in the unit data -->
  <div class="way-forward-box">
    <strong>Way Forward:</strong> [Constructive path forward/recommendations from the source text]
  </div>

  <!-- Include this box ONLY for units with content_depth "full" or "medium" -->
  <div class="scan-analysis-box">
    <strong>SCAN Analysis:</strong>
    <ul>
      <li><span class="scan-label scan-s">S — Situation:</span> [Dig below the surface level. Identify the underlying structural problem and systemic root causes]</li>
      <li><span class="scan-label scan-c">C — Consequences:</span> [Map out a 360-degree view of how the event or policy impacts multiple stakeholders—especially vulnerable groups like salaried middle class, senior citizens, or small businesses]</li>
      <li><span class="scan-label scan-a">A — Alternatives:</span> [Weigh choices and analyze what else could have been done, acknowledging the trade-offs and selecting the better public administration option]</li>
      <li><span class="scan-label scan-n">N — Next Step:</span> [Structured timeline-oriented action plan. Explicit steps to execute in the short, mid, and long term as if you were the Officer-in-Charge or District Magistrate (DM)]</li>
    </ul>
  </div>

  <p class="gs-tag"><strong>GS</strong>: Paper & Topic | <strong>Prelims</strong>: key terms, schemes, institutions | <strong>Mains</strong>: one-line answer angle</p>
</div>

ABSOLUTE RULES:
1. Number each article card sequentially (1, 2, 3...).
2. Start with `<div class="brief-card">` immediately. Output NOTHING before it — no greeting, no introduction, no explanation. NOTHING.
3. End with the last `</div>` tag. Output NOTHING after.
4. Use ONLY standard HTML tags (div, span, table, tr, td, h3, p, strong, em, ul, li). No markdown (like ###, **, ---, *).
5. STATE ONLY WHAT THE SOURCE SAYS. Do NOT speculate, infer, or add information not present in the source material.
6. Inline Source Attributions: Explicitly include source references inside the text (e.g. "...[The Hindu] reports that..." or "...as noted in [Indian Express]...").
7. Omit sections (prelims-metadata-card, mains-split-table, way-forward-box) if the corresponding fields in the raw unit data are empty or consist entirely of "N/A".
8. The <p class="gs-tag"> line is MANDATORY for every article.
9. Multi-Source Perspective Synthesis (Editorial Contrast): If a unit lists multiple sources in its "sources" field (e.g. both "The Hindu" and "Indian Express"), synthesize their points and explicitly contrast any differing editorial perspectives or focuses inline inside the summary paragraph (e.g., "While [The Hindu] emphasizes the federalism concerns of the bill, [Indian Express] focuses on its administrative efficiency gains").
10. Static Sync Tag: Retrieve the "static_links" list from the unit data and print it inside the `<span class="static-tag">` element. If no static links are present, output "N/A".
11. SCAN Method implementation: The `scan-analysis-box` MUST be populated ONLY for articles that have `content_depth` equal to "full" or "medium". For articles with `content_depth` equal to "concise" or "prelims_only", do NOT include the `scan-analysis-box` block at all (omit it completely from the HTML output). Dig deep into the structural, stakeholder, trade-off, and implementation action plan aspects for full/medium articles to build the required administrative mindset.
12. Three Lenses integration: Apply the appropriate lens based on the nature of the article:
    - Policy Articles (Governance Lens): Focus on how a government policy solves a specific issue. Identify who was previously excluded, which vulnerable group benefits now, and foresee potential implementation challenges. Think about the metrics/data required a year later to evaluate if the policy succeeded.
    - Crisis Articles (Administrative Lens): For disasters, industrial accidents, or infrastructure failures, avoid purely emotional narratives. Analyze what failed within the local administration, which existing regulatory framework can be improved, and which agency holds structural accountability.
    - Opinions & Op-Eds (Reasoning Lens): Dissect the logic and framework of reasoning. Learn how experts frame arguments, address counter-arguments, and defend their perspective.
13. Strict Exclusions: Strictly exclude hyper-specific sensationalism or local crime. Do not include details of regional tragedies with no administrative takeaway (e.g., exact casualty counts, nationalities, or locations of localized municipal fires). Also strictly exclude all political drama, party rivalry, seat sharing, defection, election campaigning, or political attacks that have no substantive administrative or policy significance.

BANNED PHRASES — Do NOT use any of these:
"This is significant because", "It is worth noting", "In a landmark move",
"In a significant development", "The move is expected to", "This marks a",
"Crucially", "Notes that", "Notes that", "Notably", "Importantly", "Interestingly",
"game-changer", "historic", "path-breaking", "watershed moment",
"bold step", "major boost", "much-needed", "long-awaited",
"sends a strong signal", "remains to be seen", "only time will tell"

TONE: Factual, neutral, exam-focused, and specific.

SECTION: {section_name}
SECTION DESCRIPTION: {section_description}

Return ONLY the HTML articles. Nothing else."""


EDITORIAL_WRITER_PROMPT = """You are a UPSC Editorial Brief Writer. Produce compact, argument-focused editorial summaries for serious UPSC aspirants.

YOUR OUTPUT FORMAT — for each editorial, produce EXACTLY this HTML structure:

<div class="brief-card">
  <h3>1. Editorial Title</h3>
  <p><strong>Argument:</strong> Central thesis in 1-2 sentences, as stated by the author.</p>
  <p><strong>Key Points:</strong> 2-3 most important arguments or evidence points from the editorial. Use bullet format with <em>•</em> separators.</p>
  <p><strong>Counter:</strong> Alternative perspective or limitation acknowledged in the piece, in 1 sentence.</p>

  <!-- SCAN Analysis Box -->
  <div class="scan-analysis-box">
    <strong>SCAN Analysis:</strong>
    <ul>
      <li><span class="scan-label scan-s">S — Situation:</span> [Dig below the surface level. Identify the underlying structural problem and systemic root causes]</li>
      <li><span class="scan-label scan-c">C — Consequences:</span> [Map out a 360-degree view of how the event or policy impacts multiple stakeholders—especially vulnerable groups like salaried middle class, senior citizens, or small businesses]</li>
      <li><span class="scan-label scan-a">A — Alternatives:</span> [Weigh choices and analyze what else could have been done, acknowledging the trade-offs and selecting the better public administration option]</li>
      <li><span class="scan-label scan-n">N — Next Step:</span> [Structured timeline-oriented action plan. Explicit steps to execute in the short, mid, and long term as if you were the Officer-in-Charge or District Magistrate (DM)]</li>
    </ul>
  </div>

  <p class="gs-tag"><strong>GS</strong>: Paper & Topic | <strong>Mains</strong>: answer framing angle</p>
</div>

ABSOLUTE RULES:
1. Number each editorial sequentially (1, 2, 3...).
2. Start with `<div class="brief-card">` immediately. Output NOTHING before the first tag.
3. End with the last `</div>` tag. Output NOTHING after.
4. Use ONLY HTML tags. No markdown syntax.
5. Maximum 220 words per editorial card, keeping the SCAN analysis concise.
6. STATE ONLY WHAT THE SOURCE SAYS. Do NOT add your own arguments or analysis.
7. The <p class="gs-tag"> line is MANDATORY.
8. For Counter: if the editorial doesn't present a counterview, write "Not addressed in the piece."
9. SCAN Method: The `scan-analysis-box` MUST be populated for every editorial, following the SCAN structure (Situation, Consequences, Alternatives, Next Step) to build the required administrative mindset.
10. Reasoning Lens: Dissect the logic and framework of reasoning. Show how experts frame arguments, address counter-arguments, and defend their perspective.
11. Strict Exclusions: Exclude regional/local crime and sensationalism. Focus on systemic, structural, and administrative takeaways.

BANNED PHRASES — Do NOT use any of these:
"This is significant because", "It is worth noting", "In a landmark move",
"Crucially", "Notes that", "Notably", "game-changer", "historic", "path-breaking"

TONE: Analytical and neutral. Report the author's argument faithfully without endorsing or editorializing.

Return ONLY the HTML editorials. Nothing else."""


# Word caps by content depth
WORD_CAP_MAP = {
    ContentDepth.FULL.value: 180,
    ContentDepth.MEDIUM.value: 100,
    ContentDepth.CONCISE.value: 50,
    ContentDepth.PRELIMS_ONLY.value: 30,
}


def get_section_prompt(section_name: str, content_depths: list[str] | None = None) -> str:
    """Get the appropriate writing prompt for a section."""
    config = SECTION_CONFIG.get(section_name, {})

    if section_name == SectionName.EDITORIAL.value:
        return EDITORIAL_WRITER_PROMPT

    # Determine dominant word cap for this batch
    word_cap = 80  # default
    if content_depths:
        # Use the highest depth's word cap for the batch
        for depth in [ContentDepth.FULL.value, ContentDepth.MEDIUM.value,
                      ContentDepth.CONCISE.value, ContentDepth.PRELIMS_ONLY.value]:
            if depth in content_depths:
                word_cap = WORD_CAP_MAP.get(depth, 80)
                break

    return SECTION_WRITER_SYSTEM_PROMPT.format(
        section_name=config.get("display_name", section_name),
        section_description=config.get("description", ""),
        word_cap=word_cap,
    )


def clean_html_fragment(text: str) -> str:
    """Post-process LLM response: strip ALL non-HTML content aggressively."""
    if not text:
        return ""

    # Trim whitespace
    text = text.strip()

    # Remove markdown code block markers
    text = re.sub(r'```html\s*', '', text)
    text = re.sub(r'```\s*', '', text)

    # Remove instructions blocks that LLMs sometimes output in the middle or end (run first while raw markdown is intact)
    text = re.sub(r'[ \t]*--- \*\*TO PROCESS OTHER UNITS.*?(?:Here is the transformed content\.\.\.\s*---[ \t]*|[ \t]*---[ \t]*)', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'[ \t]*--- \*\*TO PROCESS.*', '', text, flags=re.DOTALL | re.IGNORECASE)

    # Convert remaining markdown headings to HTML first (so they aren't stripped by tag search)
    text = re.sub(r'#####\s+\*\*(.*?)\*\*', r'<h5>\1</h5>', text)
    text = re.sub(r'#####\s+(.*?)(?=\n|<|$)', r'<h5>\1</h5>', text)
    text = re.sub(r'####\s+\*\*(.*?)\*\*', r'<h4>\1</h4>', text)
    text = re.sub(r'####\s+(.*?)(?=\n|<|$)', r'<h4>\1</h4>', text)
    text = re.sub(r'###\s+\*\*(.*?)\*\*', r'<h3>\1</h3>', text)
    text = re.sub(r'###\s+(.*?)(?=\n|<|$)', r'<h3>\1</h3>', text)

    # Clean markdown bold/italic inside HTML headings
    text = re.sub(r'(<h[2345]>)\s*\*\*?\s*(.*?)\s*\*\*?\s*(</h[2345]>)', r'\1\2\3', text)

    # Convert markdown bold/italic to HTML
    text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)

    # Deduplicate adjacent headings if one's text is contained in the other
    def remove_duplicate_headings(m):
        h1_tag = m.group(1)
        h1_text = m.group(2)
        h2_tag = m.group(3)
        h2_text = m.group(4)
        t1 = re.sub(r'^\d+\.\s*', '', h1_text.strip()).lower()
        t2 = re.sub(r'^\d+\.\s*', '', h2_text.strip()).lower()
        if t1 in t2 or t2 in t1:
            return f"<{h2_tag}>{h2_text}</{h2_tag}>"
        return m.group(0)

    text = re.sub(r'<(h[1-6])>(.*?)</\1>\s*<(h[1-6])>(.*?)</\3>', remove_duplicate_headings, text, flags=re.DOTALL | re.IGNORECASE)

    # AGGRESSIVE LEADING TEXT REMOVAL:
    # Find the first HTML tag and remove everything before it
    first_tag = re.search(r'<(?:h[1-6]|div|p|table|ul|ol|section|article)', text, re.IGNORECASE)
    if first_tag:
        leading_text = text[:first_tag.start()]
        # If leading text contains a closing tag, we are in the middle of a block; do not strip.
        if '</' not in leading_text:
            text = text[first_tag.start():]

    # AGGRESSIVE TRAILING TEXT REMOVAL:
    # Find the last closing HTML tag and remove everything after it
    last_close = None
    for m in re.finditer(r'</(?:h[1-6]|div|p|table|ul|ol|section|article|tr|td|th|li)>', text, re.IGNORECASE):
        last_close = m
    if last_close:
        text = text[:last_close.end()]

    # Remove horizontal rule markdown "---"
    text = re.sub(r'^-{3,}\s*$', '', text, flags=re.MULTILINE)

    # Remove any remaining stray markdown heading markers
    text = re.sub(r'(?<!<)#####\s*', '', text)
    text = re.sub(r'(?<!<)####\s*', '', text)
    text = re.sub(r'(?<!<)###\s*', '', text)

    # Remove conversational lines that may have survived the tag-based stripping
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip conversational intros/outros
        if any(stripped.lower().startswith(pat) for pat in [
            "here is the", "here is a", "here are the",
            "i have selected", "i've selected", "i have provided",
            "if you'd like me", "let me know", "please request",
            "below is the", "i'll provide", "to request",
            "note:", "please note", "i'll format",
            "the following", "as requested",
            "sure, here", "certainly", "of course",
            "based on the", "after reviewing",
            "i've analyzed", "i have analyzed",
        ]):
            continue
        cleaned_lines.append(stripped)

    text = "\n".join(cleaned_lines).strip()

    # Final pass: remove any banned editorializing phrases that leaked through
    banned_phrases = [
        r"[Tt]his is significant because",
        r"[Ii]t is worth noting",
        r"[Ii]n a landmark move,?\s*",
        r"[Ii]n a significant development,?\s*",
        r"[Tt]he move is expected to",
        r"[Cc]rucially,?\s*",
        r"[Nn]otably,?\s*",
        r"[Ii]mportantly,?\s*",
        r"[Ii]nterestingly,?\s*",
    ]
    for phrase in banned_phrases:
        text = re.sub(phrase, "", text)

    # Resolve syllabus codes dynamically in syllabus-tag
    from app.utils.syllabus_app import SYLLABUS_MAP
    def resolve_syllabus(m):
        content = m.group(1)
        # Parse individual codes (split by comma, clean whitespace)
        codes = [c.strip() for c in content.split(",") if c.strip()]
        resolved = []
        for code in codes:
            clean_code = code.rstrip('.')
            if clean_code in SYLLABUS_MAP:
                desc = SYLLABUS_MAP[clean_code]
                short_desc = desc.split(".")[0]
                if len(short_desc) > 60:
                    short_desc = short_desc[:57] + "..."
                resolved.append(f"{clean_code} ({short_desc})")
            else:
                resolved.append(code)
        return f'<span class="syllabus-tag">Syllabus: {", ".join(resolved)}</span>'

    text = re.sub(r'<span class="syllabus-tag">Syllabus:\s*(.*?)</span>', resolve_syllabus, text, flags=re.IGNORECASE)

    # Strip N/A rows from prelims-metadata-card tables
    # Remove individual <tr> rows where the value cell is just "N/A"
    text = re.sub(
        r'<tr>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>\s*N/A\s*</td>\s*</tr>',
        '', text, flags=re.DOTALL | re.IGNORECASE
    )
    # Remove the entire prelims-metadata-card if the table is now empty
    text = re.sub(
        r'<div class="prelims-metadata-card">\s*<table>\s*</table>\s*</div>',
        '', text, flags=re.DOTALL | re.IGNORECASE
    )

    return text


def _inject_anchors_and_back_buttons(html: str, batch_units: list[dict]) -> str:
    """Inject per-article anchor IDs and running element Back to Revision buttons.

    Each <h3> in the LLM output corresponds to a unit in the batch (in order).
    We prepend an <a id="unit_id"></a> anchor before each <h3> so the revision
    table can link directly to individual articles, and we append a back-to-revision
    link wrapped in a running element container.
    """
    if not html:
        return html

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        h3s = soup.find_all("h3")

        for i, h3 in enumerate(h3s):
            if i >= len(batch_units):
                break

            unit = batch_units[i]
            unit_id = unit.get("unit_id", "")
            if not unit_id:
                continue

            # 1. Prepend the anchor to the h3
            anchor = soup.new_tag("a", id=unit_id)
            h3.insert_before(anchor)

            # 2. Check if h3 is inside a div.brief-card
            parent_card = h3.find_parent("div", class_="brief-card")

            if not parent_card:
                # Wrap this article block in a brief-card
                card = soup.new_tag("div", class_="brief-card")
                anchor.insert_before(card)

                next_h3 = h3s[i + 1] if i + 1 < len(h3s) else None
                curr = anchor
                while curr and curr != next_h3:
                    next_sib = curr.next_sibling
                    card.append(curr)
                    curr = next_sib
                parent_card = card

            # 3. Add the back-to-revision button running element inside the parent_card
            back_container = soup.new_tag("div", **{"class": "back-to-rev-container"})
            back_btn = soup.new_tag("a", href=f"#rev_{unit_id}", **{"class": "back-to-revision-btn"})
            back_btn.string = "Back to Revision Sheet"
            back_container.append(back_btn)
            parent_card.append(back_container)

        return str(soup)
    except Exception as e:
        log.warning("failed_to_inject_anchors_and_back_buttons", error=str(e))
        # Fallback to simple regex anchor injection if bs4 fails
        h3_matches = list(re.finditer(r'<h3[^>]*>', html, re.IGNORECASE))
        for i in reversed(range(len(h3_matches))):
            if i < len(batch_units):
                unit_id = batch_units[i].get("unit_id", "")
                if unit_id:
                    pos = h3_matches[i].start()
                    anchor = f'<a id="{unit_id}"></a>'
                    html = html[:pos] + anchor + html[pos:]
        return html

def write_sections(state: dict) -> dict:
    """
    Section Writer Agent: Write sections from verified units in parallel.

    Uses a ThreadPoolExecutor to run LLM section-writing batches concurrently.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from app.services.llm_client_app import LLMClient
    from app.services.settings_app import get_settings

    settings = get_settings()
    section_buffers = state.get("section_buffers", {})
    verified_units = state.get("verified_units", [])
    run_id = state.get("run_id", "unknown")

    log.info("section_writing_start", run_id=run_id, sections=list(section_buffers.keys()))

    # Build article to source mapping
    articles_normalized = state.get("articles_normalized", state.get("articles_raw", []))
    article_source_map = {}
    for a in articles_normalized:
        art_id = a.get("article_id") or a.get("url")
        if art_id:
            article_source_map[art_id] = a.get("source", a.get("source_name", ""))

    # Build unit lookup
    unit_map = {u["unit_id"]: u for u in verified_units}

    section_fragments: dict[str, list[str]] = {}
    errors = []

    # Only process sections that have a writer config
    ordered_sections = sorted(
        [s for s in section_buffers.keys() if s in SECTION_CONFIG],
        key=lambda s: SECTION_CONFIG.get(s, {}).get("order", 99),
    )

    # 1. Collect all writing tasks (batches)
    tasks = []
    for section_name in ordered_sections:
        buffer_items = section_buffers[section_name]
        if not buffer_items:
            continue

        config = SECTION_CONFIG.get(section_name, {})
        display_name = config.get("display_name", section_name)

        # Collect verified units for this section
        section_units = []
        for item in buffer_items:
            unit = unit_map.get(item["unit_id"])
            if unit:
                # Resolve source names for the articles in this unit
                unit_sources = [article_source_map.get(aid) for aid in unit.get("article_ids", [])]
                unit_sources = [s for s in unit_sources if s]
                
                # Make a dictionary copy to add custom fields for the LLM
                unit_dict = dict(unit)
                unit_dict["sources"] = list(set(unit_sources))
                unit_dict["content_depth"] = item.get("content_depth", "medium")
                unit_dict["priority"] = item.get("priority", 5)
                section_units.append(unit_dict)

        if not section_units:
            continue

        # Helper functions to classify unit types for batch sizing
        def is_long_editorial(u: dict) -> bool:
            u_str = json.dumps(u, default=str)
            # If editorial or full content depth and large, or simply extremely large
            is_edit = (u.get("content_depth") == "full" or section_name == "editorial")
            return (is_edit and len(u_str) > 6000) or len(u_str) > 10000

        def is_prelims_booster(u: dict) -> bool:
            return u.get("content_depth") == "prelims_only" or section_name == "prelims_booster"

        # Create batches adaptively based on character size and depth of units
        batches = []
        current_batch = []
        current_char_count = 0
        max_batch_chars = 30000

        base_limit = settings.writer_batch_size if settings.writer_batch_size else 4
        limit_prelims = max(10, base_limit) if base_limit >= 4 else base_limit
        limit_regular = min(4, base_limit)
        limit_long = min(2, base_limit)

        for unit in section_units:
            unit_size = len(json.dumps(unit, default=str))
            u_is_long = is_long_editorial(unit)
            u_is_prelims = is_prelims_booster(unit)

            # Count existing in current batch
            num_long_in_batch = sum(1 for u in current_batch if is_long_editorial(u))
            all_prelims_in_batch = all(is_prelims_booster(u) for u in current_batch) if current_batch else True

            if current_batch:
                if all_prelims_in_batch and u_is_prelims:
                    max_batch_units = limit_prelims
                elif num_long_in_batch >= 2 and u_is_long:
                    # Adding this long editorial would make it 3. We auto-reduce the batch size to 2 to force a split.
                    max_batch_units = limit_long
                else:
                    max_batch_units = limit_regular
            else:
                max_batch_units = limit_prelims if u_is_prelims else (limit_long if u_is_long else limit_regular)

            if current_batch and (len(current_batch) >= max_batch_units or current_char_count + unit_size > max_batch_chars):
                batches.append(current_batch)
                current_batch = []
                current_char_count = 0
                max_batch_units = limit_prelims if u_is_prelims else (limit_long if u_is_long else limit_regular)

            current_batch.append(unit)
            current_char_count += unit_size

        if current_batch:
            batches.append(current_batch)

        # Create tasks for each batch
        batch_start_idx = 1
        for batch in batches:
            batch_depths = [u.get("content_depth", "medium") for u in batch]
            batch_end_idx = batch_start_idx + len(batch) - 1
            tasks.append({
                "section_name": section_name,
                "display_name": display_name,
                "batch": batch,
                "batch_idx": len(tasks),
                "batch_range": f"{batch_start_idx}-{batch_end_idx}",
                "content_depths": batch_depths,
            })
            batch_start_idx = batch_end_idx + 1

    if not tasks:
        return {
            "section_fragments": {},
            "errors": [],
            "current_phase": "sections_written",
        }

    # Thread worker function
    def write_single_batch(task: dict) -> tuple[str, str | None, dict | None, int, int]:
        # Returns (section_name, html_fragment, error_dict, calls, tokens)
        section_name = task["section_name"]
        display_name = task["display_name"]
        batch = task["batch"]
        batch_range = task["batch_range"]
        content_depths = task.get("content_depths", [])
        
        llm = LLMClient(
            api_key=settings.nim_api_key,
            base_url=settings.nim_base_url,
            model=settings.nim_model,
            max_retries=settings.llm_max_retries,
            timeout=settings.llm_timeout,
            delay=settings.llm_delay_seconds,
        )
        try:
            prompt = get_section_prompt(section_name, content_depths)
            units_text = json.dumps(batch, default=str, indent=2)

            html_fragment = llm.write_section(
                system_prompt=prompt,
                verified_units_json=units_text,
                section_name=display_name,
            )

            if html_fragment:
                # Post-process to remove markdown and conversational boilerplate
                html_fragment = clean_html_fragment(html_fragment)
                # Inject per-article anchors and back-to-revision buttons
                html_fragment = _inject_anchors_and_back_buttons(html_fragment, batch)
                log.info(
                    "batch_written",
                    section=section_name,
                    batch=batch_range,
                    chars=len(html_fragment),
                )
                return section_name, html_fragment, None, llm.total_calls, llm.total_tokens
            else:
                log.warning("empty_section_batch_output", section=section_name, batch=batch_range)
                raise ValueError(f"Empty section batch output returned by LLM for section {section_name} batch {batch_range}")

        except Exception as e:
            log.error(
                "section_write_error",
                section=section_name,
                batch=batch_range,
                error=str(e),
            )
            raise e

    # 2. Execute tasks in parallel
    max_workers = min(len(tasks), 4)
    total_calls = 0
    total_tokens = 0
    log.info("section_writing_parallel_start", workers=max_workers, total_batches=len(tasks))

    # Keep a dict of task_idx -> fragment to preserve order
    ordered_results: list[tuple[str, str]] = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # We submit the index so we can keep ordering intact
        futures = {executor.submit(write_single_batch, t): t for t in tasks}
        
        for future in as_completed(futures):
            task = futures[future]
            try:
                section_name, html_fragment, error_dict, calls, tokens = future.result()
                total_calls += calls
                total_tokens += tokens
                
                if html_fragment:
                    # We store it along with its original batch index to sort later
                    ordered_results.append((section_name, task["batch_idx"], html_fragment))
                if error_dict:
                    errors.append(error_dict)
            except Exception as e:
                log.error("thread_writer_failed", section=task["section_name"], error=str(e))
                errors.append({
                    "phase": "write_sections",
                    "article_id": task["section_name"],
                    "error_type": type(e).__name__,
                    "message": str(e)[:500],
                })

    # Sort results by the original batch index to ensure sequential consistency
    ordered_results.sort(key=lambda x: x[1])

    # Re-group by section_name
    for section_name in ordered_sections:
        fragments = [r[2] for r in ordered_results if r[0] == section_name]
        if fragments:
            section_fragments[section_name] = fragments

    log.info(
        "section_writing_complete",
        run_id=run_id,
        sections_written=len(section_fragments),
        total_fragments=sum(len(f) for f in section_fragments.values()),
        llm_stats={"total_calls": total_calls, "total_tokens": total_tokens},
    )

    try:
        run_date = state.get("run_date", "unknown")
        output_file = settings.scraper_output_path / f"written_sections_{run_date}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(section_fragments, f, indent=2, default=str)
        log.info("section_writing_results_saved", path=str(output_file))
    except Exception as e:
        log.error("failed_to_save_section_writing_results", error=str(e))

    return {
        "section_fragments": section_fragments,
        "errors": errors,
        "current_phase": "sections_written",
    }
