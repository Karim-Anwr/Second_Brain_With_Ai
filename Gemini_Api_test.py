import google.generativeai as genai

genai.configure(api_key= settings.gemini_api_key)

model = genai.GenerativeModel("gemini-2.0-flash")

response = model.generate_content("hello")

print(response.text)