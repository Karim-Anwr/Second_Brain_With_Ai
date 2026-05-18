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
  "memory_id": "mem_60b1104ae1da",
  "file_name": "Screenshot_2023-08-07-10-25-38-76_680d03679600f7af0b4c700c6b270fe7.jpg",
  "file_type": "image",
  "summary": "10:25 62 15 tea ا til Ga) 81 SY مقدمة صور ١ فيديو ١ قصة معالشرح يا La زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي لك إبطاء المذل المنعم وتجني القادر المحتكم والثواني جمرات في دمي إنني أعطيت ما استبقيت شيّ إنني أعطيت ...",
  "tags": [],
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
  "query": " كان في اغنيه الاطلال لام كلثوم هنا طائر الشوق أغني ألمي ",
  "total": 1,
  "results": [
    {
      "memory_id": "mem_60b1104ae1da",
      "file_name": "Screenshot_2023-08-07-10-25-38-76_680d03679600f7af0b4c700c6b270fe7.jpg",
      "file_path": "storage/uploads/f31fa555-281f-4e69-9a57-033c4284b09a.jpg",
      "summary": "10:25 62 15 tea ا til Ga) 81 SY مقدمة صور ١ فيديو ١ قصة معالشرح يا La زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي لك إبطاء المذل المنعم وتجني القادر المحتكم والثواني جمرات في دمي إنني أعطيت ما استبقيت شيّ إنني أعطيت ...",
      "matched_text": "10:25 62 15 tea ا til Ga) 81 SY مقدمة صور ١ فيديو ١ قصة معالشرح يا La زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي يا حبيباً زرت يوماً أيكه طائر الشوق أغني ألمي لك إبطاء المذل المنعم وتجني القادر المحتكم والثواني جمرات في دمي إنني أعطيت ما استبقيت شيّ إنني أعطيت ما استبقيت شيّ oy ol قيدك أدمى معصمى ١ آه من قيدك أدمى eee لم أبقيه وما أبقى علي ما احتفاظي بعهود لم تصنها وإلام الأسر والدنيا لدي إنني أعطيت ما استبقيت شي إنني أعطيت ما استبقيت شىّ an al قيدك أدمى معصمى آه من قيدك أدمى ee لم أبقيه وما أبقى علي ما احتفاظي بعهود لم تصنها وإلام الأسر والدنيا لدي 3 Q Al Discover Search Saved",
      "tags": [
        ""
      ],
      "created_at": "2026-05-18T19:21:37.469307",
      "scores": {
        "final": 0.535,
        "semantic": 0.262,
        "recency": 1,
        "importance": 0.5
      }
    }
  ],
  "llm_answer": ""
}
```

