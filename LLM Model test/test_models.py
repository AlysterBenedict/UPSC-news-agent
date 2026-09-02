import os, time, json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

models_to_test = [
    ('deepseek-ai/deepseek-v4-pro-0813', 'DeepSeek V4 Pro'),
    ('mistralai/mistral-large-2-instruct', 'Mistral Large 2 (123B)'),
    ('meta/llama-3.2-90b-vision-instruct', 'Llama 3.2 90B Vision Instruct'),
    ('openai/gpt-oss-120b', 'GPT OSS 120B'),
    ('openai/gpt-oss-20b', 'GPT OSS 20B'),
    ('nvidia/nemotron-3.5-lightning-30b-a3b', 'Nemotron 3.5 Lightning 30B')
]

schema_str = json.dumps({
    "title": "string",
    "factual_summary": ["fact 1"],
    "why_it_matters": ["point 1"],
    "gs_papers": ["GS3"],
    "syllabus_codes": ["GS3.5"],
    "prelims_facts": ["fact 1"]
}, indent=2)

prompt = f"""You are a UPSC Current Affairs Analysis Expert. Return ONLY valid JSON matching this schema:
{schema_str}

Article: The Reserve Bank of India (RBI) on Thursday increased risk weights on unsecured consumer loans from banks and NBFCs by 25 percentage points to 125%, citing rapid credit expansion.
"""

print("=== EVALUATING ACCURACY, FORMAT COMPLIANCE & SPEED ===")
for m_id, name in models_to_test:
    t0 = time.perf_counter()
    try:
        res = client.chat.completions.create(
            model=m_id,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.1
        )
        t1 = time.perf_counter()
        raw = res.choices[0].message.content or ""
        clean_raw = raw.strip()
        if "```json" in clean_raw:
            clean_raw = clean_raw.split("```json")[1].split("```")[0].strip()
        elif "```" in clean_raw:
            clean_raw = clean_raw.split("```")[1].split("```")[0].strip()
        
        try:
            parsed = json.loads(clean_raw)
            json_valid = True
            keys_ok = all(k in parsed for k in ["title", "factual_summary", "why_it_matters", "gs_papers", "syllabus_codes", "prelims_facts"])
        except Exception:
            json_valid = False
            keys_ok = False
            
        print(f"[{name}] | Model: {m_id} | Time: {t1-t0:.2f}s | Valid JSON: {json_valid} | Schema Match: {keys_ok}")
    except Exception as e:
        print(f"[{name}] | Model: {m_id} | FAILED: {e}")
