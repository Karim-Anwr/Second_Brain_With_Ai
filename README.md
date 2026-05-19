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
  "memory_id": "mem_fffe801a25d1",
  "file_name": "Screenshot_٢٠٢٢-٠٧-٣٠-٢٠-١١-٠٨-٢١_b5f6883d2c20a96c53babc0b4ac88108.jpg",
  "file_type": "image",
  "summary": "العلامة التجارية جينيرك تقدم مضرب البيض المحمولة الفولاذ المقاوم للصدا. يمكن استخدام هذا المضرب لقهوة، حليب، وخيارات أخرى. يأتي باللون الأسود.",
  "tags": [
    "مضرب البيض",
    "علبة خفق",
    "أدوات المطبخ",
    "الطبخ",
    "القهوة",
    "الحليب"
  ],
  "category": "other",
  "importance": 0.5,
  "total_chunks": 1,
  "status": "success"
}
```

---

### Search your documents

```bash
curl -X POST http://localhost:8000/api/v1/search \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning notes", "top_k": 5}'
```

**Response:**
```json
{
  "query": "كان في مضرب بيض كده كنت جايبو من فتره عاوز اعرف هو بكام",
  "total": 1,
  "results": [
    {
      "memory_id": "mem_fffe801a25d1",
      "file_name": "Screenshot_٢٠٢٢-٠٧-٣٠-٢٠-١١-٠٨-٢١_b5f6883d2c20a96c53babc0b4ac88108.jpg",
      "file_path": "storage/uploads/cd8b2f8b-35ed-4df0-9aca-99cf97f05d06.jpg",
      "summary": "العلامة التجارية جينيرك تقدم مضرب البيض المحمولة الفولاذ المقاوم للصدا. يمكن استخدام هذا المضرب لقهوة، حليب، وخيارات أخرى. يأتي باللون الأسود.",
      "matched_text": "العلامة التجارية: جينيرك مضرب البيض - أدوات البيض الفولاذ المقاوم للصداً المحمولة القهوة الحليب الخفاقة مقبض خفق خلاط أدوات المطبخ أدوات الطبخ (أسود) 40 0 اللون:أسود",
      "tags": [
        "مضرب البيض",
        "علبة خفق",
        "أدوات المطبخ",
        "الطبخ",
        "القهوة",
        "الحليب"
      ],
      "created_at": "2026-05-19T13:54:52.623982",
      "scores": {
        "final": 0.433,
        "semantic": 0.167,
        "recency": 1,
        "importance": 0.5
      }
    }
  ],
  "llm_answer": ""
}
```

