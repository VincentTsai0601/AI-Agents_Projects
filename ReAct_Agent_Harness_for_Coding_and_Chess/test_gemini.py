import os

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError("找不到 GEMINI_API_KEY，請檢查 .env")

client = genai.Client(api_key=api_key)

response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents="請用繁體中文說：Gemini API 連線成功。",
)

print(response.text)