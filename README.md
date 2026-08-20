#  Second Brain — Personal Memory Search Engine

نظام ذاكرة شخصية مدعوم ب`Ai` يتيح لك رفع الصور وملفات `PDF` والنصوص والروابط من `YouTube` و`TikTok` والمواقع الإلكترونية. يفهم النظام المحتوى ويحوّله إلى معرفة قابلة للبحث، مما يسمح لك بالعثور على المعلومات باستخدام اللغة الطبيعية والتحدث معه كمساعد شخصي يتذكر كل ما حفظته مسبقًا.

---
## Core Idea

المشكلة الأصلية: بتحفظ `screenshot` `files` `links`  `notes`  كتير مهمه وبعدين بتنسى فين حفظتها أو مقدرش تلاقيها. الحل: نظام بيفهم محتوى كل حاجة بتحفظها (مش بس بيخزنها)، ويقدر يرجعلك بيها لما تسأل بأي صياغة، حتى لو مش فاكر الكلمات بالظبط.

---

## General Architecture

```
رفع محتوى (صورة/PDF/نص/لينك)
        ↓
   Ingestion Pipeline
   (OCR + Vision + LLM Analysis + Chunking)
        ↓
   Embedding (BGE-M3) → ChromaDB
        ↓
   Memory Graph (ربط تلقائي بذكريات مشابهة)

────────────────────────────

سؤال المستخدم
        ↓
   Search Pipeline
   (فهم السؤال → توسيع → Hybrid Retrieval → Rerank)
        ↓
   رد إنساني من الـ LLM

────────────────────────────

محادثة كاملة (Chat)
        ↓
   Short-term (آخر رسائل) + Long-term (ChromaDB) + Episodic (ذكريات الجلسة)
        ↓
   Context Builder → LLM → رد + استخراج ذكريات مهمة تلقائياً
```

---
---

##  Tech Stack

| الطبقة | التقنية | السبب |
|---|---|---|
| API | FastAPI | سريع، توثيق تلقائي (Swagger) |
| OCR | Tesseract + PyMuPDF | استخراج نص من صور وPDF |
| Vision | Groq Vision | فهم بصري للصور (مش بس النص المكتوب) |
| Embeddings | BGE-M3 (Sentence Transformers) | يدعم العربي والإنجليزي بقوة، 1024 بعد |
| Vector DB | ChromaDB | تخزين الـ chunks مع metadata غنية |
| LLM | Groq (Llama 3.3 / 3.1) | تحليل المحتوى، فهم الأسئلة، الرد، إعادة الترتيب |
| Audio | yt-dlp + faster-whisper | تحويل صوت الفيديوهات لنص (يوتيوب/تيك توك) |
| Links | oEmbed + Open Graph | استخراج عنوان ووصف وصورة من اللينكات |

---
---

##  Setup & Installation


### 1. Clone the project

```bash
git clone https://github.com/Karim-Anwr/Second_Brain_With_Ai.git
cd Second_Brain_With_Ai
```


### 2. Create virtual environment

```bash
python3 -m venv venv

# Linux 
source venv/bin/activate

```

### 3. Install dependencies

```bash
pip install -r app/requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
```

### Database foundation (Phase 2.1)

Phase 2.1 introduces a **migration-driven PostgreSQL foundation** only. Set `DATABASE_URL` in the untracked `.env` file to a non-production PostgreSQL database before running migrations. The application does not connect to PostgreSQL at startup and does not create tables automatically.

```bash
# Example only — use non-production credentials and do not commit them.
export DATABASE_URL='postgresql+psycopg://<user>:<password>@<host>:5432/<database>'
alembic upgrade head
```

No application tables exist in Phase 2.1; the first schema migration is intentionally deferred to Phase 2.2.

### 5. Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

API is now running at: `http://localhost:8000`

---

##  API Usage

### Upload a file

```bash
curl -X POST http://localhost:8000/api/v1/upload \
  -F "file=@/path/to/your/screenshot.png"
```

**Response:**
```json
{
  "memory_id": "mem_bcd549fedf37",
  "file_name": "Screenshot_2023-08-29-14-06-27-77_b5f6883d2c20a96c53babc0b4ac88108.jpg",
  "file_type": "image",
  "summary": "الملف يحتوي على تفاصيل جهاز كمبيوتر محمول من لينوفو، يضم معالج إنتل كور i7، 16 جيجابايت من الذاكرة العشوائية، ورسومات إنفيديا جيفورس RTX 3050. الجهاز يحتوي على شاشة 15.6 إنش بدقة 1920x1080، ويدعم تردد 120 هرتز. السعر المذكور هو 32,444 مع إمكانية إرجاع المنتج.",
  "tags": ["لينوفو", "كمبيوتر محمول", "تكنولوجيا"],
  "category": "technology",
  "importance": 0.8,
  "total_chunks": 1,
  "status": "success"
}
```

---

### Search your documents

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "كان فى صوره للاب لينوفو عاوز اعرف السعر كام", "top_k": 5}'
```

**Response:**
```json
{
  "query": "كان فى صوره للاب لينوفو عاوز اعرف السعر كام",
  "total": 1,
  "results": [
    {
      "memory_id": "mem_bcd549fedf37",
      "file_name": "Screenshot_2023-08-29-14-06-27-77_b5f6883d2c20a96c53babc0b4ac88108.jpg",
      "file_path": "storage/uploads/e9b3ef9c-62aa-480d-bdc0-73264c802134.jpg",
      "summary": "الملف يحتوي على تفاصيل جهاز كمبيوتر محمول من لينوفو، يضم معالج إنتل كور i7، 16 جيجابايت من الذاكرة العشوائية، ورسومات إنفيديا جيفورس RTX 3050. الجهاز يحتوي على شاشة 15.6 إنش بدقة 1920x1080، ويدعم تردد 120 هرتز. السعر المذكور هو 32,444 مع إمكانية إرجاع المنتج.",
      "matched_text": "الملف يحتوي على تفاصيل جهاز كمبيوتر محمول من لينوفو، يضم معالج إنتل كور i7، 16 جيجابايت من الذاكرة العشوائية، ورسومات إنفيديا جيفورس RTX 3050. الجهاز يحتوي على شاشة 15.6 إنش بدقة 1920x1080، ويدعم تردد 120 هرتز. السعر المذكور هو 32,444 مع إمكانية إرجاع المنتج.",
      "tags": [
        "لينوفو",
        "كمبيوتر محمول",
        "ألعاب",
        "إنترنت",
        "تكنولوجيا"
      ],
      "created_at": "2026-05-21T15:01:08.211352",
      "scores": {
        "final": 0.639,
        "semantic": 0.6474,
        "recency": 1,
        "importance": 0.8
      }
    }
  ],
  "llm_answer": "لقد وجدت المعلومة التي تبحث عنها 😊. الملف الذي وجدته يسمى \"Screenshot_2023-08-29-14-06-27-77_b5f6883d2c20a96c53babc0b4ac88108.jpg\"، وهو يحتوي على تفاصيل جهاز كمبيوتر محمول من لينوفو. الجهاز يضم معالج إنتل كور i7، 16 جيجابايت من الذاكرة العشوائية، ورسومات إنفيديا جيفورس RTX 3050. الشاشة هي 15.6 إنش بدقة 1920x1080، وتدعم تردد 120 هرتز. السعر المذكور هو 32,444، مع إمكانية إرجاع المنتج.\n\nلو كنت تبحث عن شيء آخر أو تحتاج لمزيد من المعلومات، أنا هنا لمساعدتك 🤔. هل هناك شيء محدد تريد معرفته عن هذا الجهاز أو تريد مقارنة أسعار أخرى؟"
}
```

