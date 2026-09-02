import os, sys, time
from openai import OpenAI
from dotenv import load_dotenv

# Ensure utf-8 output in Windows console
sys.stdout.reconfigure(encoding='utf-8')

load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

sample_editorial = """
TITLE: The digital public infrastructure revolution in India
SOURCE: The Hindu / Indian Express
TEXT: India's Digital Public Infrastructure (DPI), led by Aadhaar, UPI, and DigiLocker, has revolutionized public service delivery and financial inclusion. Over the last decade, UPI transactions have surpassed billions monthly, lowering transaction costs and curbing leakages in direct benefit transfers. However, significant structural challenges remain. Digital exclusion due to poor rural connectivity, lack of digital literacy among women and marginalized groups, and rising cybersecurity threats pose severe vulnerabilities. Furthermore, data protection and privacy concerns persist in the absence of stringent enforcement mechanisms. The government must balance innovation with robust data governance, universal digital literacy drives, and resilient cyber infrastructure to ensure equitable growth.
"""

prompt = f"""You are a UPSC Editorial Brief Writer. Produce compact, argument-focused editorial summaries for serious UPSC aspirants.

YOUR OUTPUT FORMAT — for each editorial, produce EXACTLY this HTML structure:

<div class="brief-card">
  <h3>1. Editorial Title</h3>
  <p><strong>Argument:</strong> Central thesis in 1-2 sentences, as stated by the author.</p>
  <p><strong>Key Points:</strong> 2-3 most important arguments or evidence points from the editorial. Use bullet format with <em>•</em> separators.</p>
  <p><strong>Counter:</strong> Alternative perspective or limitation acknowledged in the piece, in 1 sentence.</p>

  <!-- SCAN Analysis Box (Keep each point concise to fit cleanly inside this card) -->
  <div class="scan-analysis-box">
    <strong>SCAN Analysis:</strong>
    <ul>
      <li><span class="scan-label scan-s">S — Situation:</span> [Dig below surface level. Identify systemic root cause in 1-2 concise lines]</li>
      <li><span class="scan-label scan-c">C — Consequences:</span> [360-degree impact on key stakeholders / vulnerable groups in 1-2 concise lines]</li>
      <li><span class="scan-label scan-a">A — Alternatives:</span> [Weigh choices, policy trade-offs, and administrative options in 1-2 concise lines]</li>
      <li><span class="scan-label scan-n">N — Next Step:</span> [Short/mid/long-term actionable roadmap as Officer-in-Charge in 1-2 concise lines]</li>
    </ul>
  </div>

  <p class="gs-tag"><strong>GS</strong>: Paper & Topic | <strong>Mains</strong>: answer framing angle</p>
</div>

ABSOLUTE RULES:
1. Number each editorial sequentially (1, 2, 3...).
2. Start with `<div class="brief-card">` immediately. Output NOTHING before the first tag.
3. End with the last `</div>` tag. Output NOTHING after.
4. Use ONLY HTML tags. No markdown syntax.
5. Maximum 220 words per editorial card total, keeping the SCAN analysis punchy and concise so the entire card stays self-contained.
6. STATE ONLY WHAT THE SOURCE SAYS. Do NOT add your own arguments or analysis.
7. The <p class="gs-tag"> line is MANDATORY and must be placed inside the `<div class="brief-card">`.

ARTICLE CONTENT:
{sample_editorial}
"""

models_to_test = [
    'nvidia/nemotron-3-super-120b-a12b',
    'nvidia/nemotron-3-ultra-550b-a55b'
]

for m in models_to_test:
    print(f"==================================================")
    print(f"TESTING: {m}")
    print(f"==================================================")
    t0 = time.perf_counter()
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=1500,
            temperature=0.2,
            timeout=60
        )
        t1 = time.perf_counter()
        choice = res.choices[0].message
        content = choice.content or ""
        reasoning = getattr(choice, 'reasoning_content', None) or ""
        print(f"Time: {t1-t0:.2f}s")
        print(f"Content length: {len(content)} chars | Reasoning length: {len(reasoning)} chars")
        print("\n--- RAW CONTENT OUTPUT ---")
        print(content)
        print("\n--- REASONING SAMPLE ---")
        print(reasoning[:200] if reasoning else "None")
    except Exception as e:
        print(f"Error: {e}")
    print("\n")
