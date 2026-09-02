import os, sys, time, json
from openai import OpenAI
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv('upsc-agent/.env')
api_key = os.environ.get('NIM_API_KEY')
client = OpenAI(base_url='https://integrate.api.nvidia.com/v1', api_key=api_key)

SYSTEM_PROMPT = """You are a UPSC Relevance Classifier. Determine whether a news article is relevant for UPSC Civil Services Exam (Prelims/Mains).
Respond ONLY with valid JSON:
{
  "relevant": true/false,
  "reason": "1 concise sentence explaining why"
}"""

test_articles = [
    {
        "id": "art_01",
        "title": "RBI hikes risk weights on unsecured consumer loans to 125%",
        "category": "Economy",
        "snippet": "The Reserve Bank of India has increased risk weights on personal loans from banks and NBFCs to curb high credit growth and systemic risks."
    },
    {
        "id": "art_02",
        "title": "Actor X spotted at airport in casual summer outfit",
        "category": "Entertainment",
        "snippet": "Bollywood superstar was seen exiting Mumbai international airport terminal today afternoon wearing designer sunglasses."
    },
    {
        "id": "art_03",
        "title": "India and France sign bilateral roadmap on defence industrial cooperation",
        "category": "International",
        "snippet": "During state visit, both countries agreed on co-development and co-production of critical defence hardware including jet engines and submarines."
    },
    {
        "id": "art_04",
        "title": "Local cricket club wins tournament in suburban Pune",
        "category": "Sports",
        "snippet": "A local cricket club defeated the challengers by 4 wickets in the final match held on Sunday."
    }
]

models = [
    "openai/gpt-oss-20b",
    "nvidia/nemotron-3.5-lightning-30b-a3b"
]

print("=== BENCHMARK: RELEVANCE CLASSIFIER ===")
for m in models:
    print(f"\n==========================================")
    print(f"Testing Model: {m}")
    print(f"==========================================")
    total_time = 0
    all_json_valid = True
    
    for art in test_articles:
        user_prompt = f"ARTICLE ID: {art['id']}\nTITLE: {art['title']}\nCATEGORY: {art['category']}\n\nSNIPPET:\n{art['snippet']}"
        t0 = time.perf_counter()
        try:
            res = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=600,
                timeout=20
            )
            t1 = time.perf_counter()
            elapsed = t1 - t0
            total_time += elapsed
            content = res.choices[0].message.content or ""
            reasoning = getattr(res.choices[0].message, "reasoning_content", None) or ""
            
            # Check JSON parseability
            parsed = None
            try:
                # clean possible code fences
                clean_text = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                parsed = json.loads(clean_text)
            except Exception:
                all_json_valid = False
            
            print(f"[{art['id']}] Latency: {elapsed:.2f}s | JSON Valid: {parsed is not None}")
            if parsed:
                print(f"   Result: Relevant={parsed.get('relevant')} | Reason={parsed.get('reason')}")
            else:
                print(f"   Raw Content Preview: {content[:150]}")
        except Exception as e:
            print(f"[{art['id']}] FAILED | Error: {e}")
            
    print(f"--> Total time for 4 classifications: {total_time:.2f}s (Avg: {total_time/len(test_articles):.2f}s/call)")
