#  Second Brain — Personal Memory Search Engine

AI-powered app to upload, store, and search your documents using natural language.

---

##  What It Does

- Upload screenshots, text , link ,images, and PDFs
- Extract text automatically using OCR
- Search your files using normal sentences (not keywords)
- Get back the most relevant results using AI

---

##  Tech Stack

| Component        | Technology                          |
|-----------------|-------------------------------------|
| Backend API      | FastAPI                             |
| OCR              | Tesseract + PyMuPDF                 |
| AI Embeddings    | Sentence Transformers               |
| Vector Database  | ChromaDB                            |
| Language         | Python 3.11+                        |

---

---

##  Setup & Installation

### 1. Prerequisites

- Python 3.11+
- Tesseract OCR installed on your system

**Install Tesseract:**

```bash
# Ubuntu
sudo apt install tesseract-ocr

```

### 2. Clone the project

```bash
git clone https://github.com/Karim-Anwr/Second_Brain_With_Ai.git
cd second-brain
```


### 3. Create virtual environment

```bash
python3 -m venv venv

# Linux 
source venv/bin/activate

```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure environment

```bash
cp .env.example .env
```

### 6. Run the server

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
  "tags": [
    "لينوفو",
    "كمبيوتر محمول",
    "ألعاب",
    "إنترنت",
    "تكنولوجيا"
  ],
  "keywords": [
    "لينوفو",
    "إنترنت",
    "كمبيوتر",
    "ألعاب",
    "تكنولوجيا",
    "معالج",
    "ذاكرة",
    "رسومات"
  ],
  "entities": [
    "لينوفو",
    "إنترنت",
    "إنفيديا"
  ],
  "topics": [
    "تكنولوجيا",
    "ألعاب"
  ],
  "category": "technology",
  "language": "ar",
  "importance": 0.8,
  "main_topic": "",
  "content_type": "مقال",
  "semantic_labels": [],
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

