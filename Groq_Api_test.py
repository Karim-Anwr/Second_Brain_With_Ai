from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.groq_api_key)

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "user", "content": "hello"}
    ]
)

print(response.choices[0].message.content)