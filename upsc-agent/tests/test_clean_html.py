import pytest
from app.agents.write_sections import clean_html_fragment

def test_clean_html_headings():
    dirty = "##### **Why It Matters** <ul> <li>Highlights the caste-based violence.</li> </ul>"
    expected = "<h5>Why It Matters</h5> <ul> <li>Highlights the caste-based violence.</li> </ul>"
    assert clean_html_fragment(dirty) == expected

def test_clean_html_convo():
    dirty = """Here is the transformed HTML content:
<h3>Topic 1</h3>
<p>Content</p>
--- **TO PROCESS OTHER UNITS OR ALL, PLEASE RESPOND WITH THE FOLLOWING DETAILS:**
1. Specify Unit(s)
"""
    expected = "<h3>Topic 1</h3>\n<p>Content</p>"
    assert clean_html_fragment(dirty) == expected

def test_clean_html_markdown_bold():
    dirty = "This is **bold text** and this is *italic*."
    expected = "This is <strong>bold text</strong> and this is <em>italic</em>."
    assert clean_html_fragment(dirty) == expected

def test_clean_html_duplicate_headings():
    dirty = "#### **1. ED Summons** <h3>ED Summons</h3>"
    expected = "<h3>ED Summons</h3>"
    assert clean_html_fragment(dirty) == expected

def test_clean_html_middle_instructions():
    dirty = """Article ID: 123 </div>
--- **TO PROCESS OTHER UNITS OR ALL, PLEASE RESPOND WITH THE FOLLOWING DETAILS:**
1. Specify Unit
```
Please process...
```
Here is the transformed content...
--- ### **GS2: Polity**"""
    expected = "Article ID: 123 </div>\n<h3>GS2: Polity</h3>"
    assert clean_html_fragment(dirty) == expected

def test_clean_html_heading_emphasis():
    dirty = "<h4>**What Happened**</h4>"
    expected = "<h4>What Happened</h4>"
    assert clean_html_fragment(dirty) == expected

