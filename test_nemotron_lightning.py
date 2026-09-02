import os, time, json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

prompt = """You are a UPSC Current Affairs Analysis Expert. Return ONLY valid JSON matching this schema:
{
  "title": "string",
  "factual_summary": ["fact 1", "fact 2"],
  "why_it_matters": ["significance 1"],
  "gs_papers": ["GS3"],
  "syllabus_codes": ["GS3.5"],
  "prelims_facts": ["fact 1"]
}

Article: The Reserve Bank of India (RBI) on Thursday increased risk weights on unsecured consumer loans from banks and NBFCs by 25 percentage points to 125%, citing rapid credit expansion.
"""

print("Testing nvidia/nemotron-3.5-lightning-30b-a3b:")
t0 = time.perf_counter()
res = client.chat.completions.create(
    model="nvidia/nemotron-3.5-lightning-30b-a3b",
    messages=[{"role": "user", "content": prompt}],
    max_tokens=350,
    temperature=0.1
)
t1 = time.perf_counter()
content = res.choices[0].message.content or ""
print(f"Latency: {t1-t0:.2f}s")
print("Output:\n", content)
