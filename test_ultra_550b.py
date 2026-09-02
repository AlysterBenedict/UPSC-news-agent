import os, time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

models_to_test = [
    'nvidia/nemotron-3-ultra-550b-a55b',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
    'nvidia/nemotron-nano-3-30b-a3b',
    'openai/gpt-oss-120b',
    'nvidia/nemotron-3.5-lightning-30b-a3b'
]

print("=== TESTING NIM AVAILABILITY & BASIC RESPONSE ===")
for m in models_to_test:
    t0 = time.perf_counter()
    try:
        res = client.chat.completions.create(
            model=m,
            messages=[{'role': 'user', 'content': 'Hello, what is the Reserve Bank of India? Answer in one short sentence.'}],
            max_tokens=60,
            timeout=20
        )
        t1 = time.perf_counter()
        content = res.choices[0].message.content
        reasoning = getattr(res.choices[0].message, 'reasoning_content', None)
        print(f"[SUCCESS] {m} | Time: {t1-t0:.2f}s")
        if content:
            print(f"   Content: {content.strip()}")
        elif reasoning:
            print(f"   Reasoning: {reasoning.strip()[:100]}...")
    except Exception as e:
        print(f"[FAIL] {m} | Error: {e}")
