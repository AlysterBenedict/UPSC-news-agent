import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from config.settings import get_settings
from app.services.llm_client import LLMClient

def test_connection():
    settings = get_settings()
    print(f"Initializing connection...")
    print(f"Model: {settings.nim_model}")
    print(f"Base URL: {settings.nim_base_url}")
    
    client = LLMClient(
        api_key=settings.nim_api_key,
        base_url=settings.nim_base_url,
        model=settings.nim_model,
        max_retries=1,  # Fast fail for test
    )
    
    try:
        print("\nSending test prompt to NVIDIA NIM...")
        response = client.generate(
            system_prompt="You are a connection tester. Reply with exactly the word SUCCESS.",
            user_prompt="Say SUCCESS.",
            max_tokens=10
        )
        print(f"Received response: '{response.strip()}'")
        if "SUCCESS" in response.upper():
            print("\n[OK] Connection successful! The LLM is responding correctly.")
        else:
            print(f"\n[WARN] Connection succeeded but response was unexpected: {response}")
    except Exception as e:
        print(f"\n[ERROR] Connection failed: {e}")

if __name__ == "__main__":
    test_connection()
