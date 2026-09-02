import os, time
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

models = ['openai/gpt-oss-120b', 'openai/gpt-oss-20b', 'deepseek-ai/deepseek-v4-pro-0813', 'deepseek-ai/deepseek-v4-flash-0731', 'google/gemma-4-31b-it']
for m in models:
    try:
        t0 = time.perf_counter()
        res = client.chat.completions.create(
            model=m,
            messages=[{'role': 'user', 'content': 'Respond with: {"status": "ok"}'}],
            max_tokens=30,
            timeout=8
        )
        t1 = time.perf_counter()
        print(f'{m}: OK ({t1-t0:.2f}s) -> {res.choices[0].message.content}')
    except Exception as e:
        print(f'{m}: FAIL -> {e}')
