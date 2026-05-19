from app.services.embedding_service import embedding_service

# اختبر نص واحد
text = "محاضرة عن الذكاء الاصطناعي في جامعة القاهرة عام 2024"
vector = embedding_service.generate(text)

print(f"النص: {text}")
print(f"حجم الـ vector: {len(vector)}")
print(f"أول 5 أرقام: {vector[:5]}")

# اختبر إن نصين متقاربين عندهم vectors متقاربة
import numpy as np

v1 = embedding_service.generate("machine learning")
v2 = embedding_service.generate("neural networks")
v3 = embedding_service.generate("وصفة كبدة بالبصل")

# cosine similarity — كلما اقتربت من 1 كلما النصين متشابهين
sim_12 = np.dot(v1, v2)
sim_13 = np.dot(v1, v3)

print(f"\nتشابه 'machine learning' و 'neural networks': {sim_12:.3f}")
print(f"تشابه 'machine learning' و 'وصفة كبدة':        {sim_13:.3f}")
print(f"\nالنتيجة المتوقعة: الأول أكبر من التاني ✅")