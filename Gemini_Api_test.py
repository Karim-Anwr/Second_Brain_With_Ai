import google.generativeai as genai
from app.core.config import settings


genai.configure(api_key= settings.gemini_api_key)

model = genai.GenerativeModel("gemini-2.5-flash")

response = model.generate_content("hello")

print(response.text)