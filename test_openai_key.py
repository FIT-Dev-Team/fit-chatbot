# test_openai_key.py
import os, openai
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
resp = openai.chat.completions.create(
    model=os.getenv("OPENAI_MODEL", os.getenv("MODEL", "gpt-4o-mini")),
    messages=[{"role":"user","content":"Hello from FIT Assistant test."}],
    max_tokens=16,
)
print("✅ OK:", resp.choices[0].message.content)