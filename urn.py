import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)

print("Checking available models for your API key...\n")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
except Exception as e:
    print(f"Error: {e}")