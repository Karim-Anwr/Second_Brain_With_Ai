import re

def clean_text(text: str) -> str:
    """
    بيتظيف النص اللي جه من OCR.
    OCR بتطلع أحياناً spaces وسطور زيادة أو رموز غريبة.
    """
    if not text:
        return ""

    # شيل أي حرف مش ASCII أو عربي أو علامة ترقيم
    text = re.sub(r'[^\w\s\u0600-\u06FF.,!?;:()\-]', ' ', text)

    # استبدل أي whitespace متعدد بمسافة واحدة
    text = re.sub(r'\s+', ' ', text)

    return text.strip()


def chunk_text(text: str, chunk_size: int = 500,
               overlap: int = 50) -> list[str]:
    """
    بيقسم النص لـ chunks بـ overlap عشان
    ما يضيعش السياق على حدود الـ chunks.
    
    مثال: لو النص 1000 كلمة وـ chunk_size=500, overlap=50:
    Chunk 1: كلمة 0   → 500
    Chunk 2: كلمة 450 → 950  ← الـ overlap بيخلي فيه تداخل
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start  = 0

    while start < len(words):
        end   = start + chunk_size
        chunk = ' '.join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap  # الـ overlap هنا

    return [c for c in chunks if len(c.strip()) > 20]