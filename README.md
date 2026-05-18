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
# Edit .env if needed — defaults work fine for local development
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
  "memory_id": "mem_151c1e22ce14",
  "file_name": "Screenshot_2022-12-17-09-22-12-47_680d03679600f7af0b4c700c6b270fe7.jpg",
  "file_type": "image",
  "summary": "9:22 d 230 481) 56 Gig بناديلك تسمعني من دونك مش بمشي لو فارق ترجعلي وتلقاني وأنا من بعدك مش بحكي لو وقتي بيسمح لي بنساني وبستناك في مكاني نفس الشوارع ونفس القهاوي برغم الفراق ساب اللي قال أن مهما الحياة دي هتصعب هيفضل معاك ما تخلي غيري يكمل مكاني وصون الوعود اللي كانت زمان وأنا بناديلك تسمعني من دو...",
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
  "query": "machine learning notes",
  "total": 2,
  "results": [
    {
      "chunk_id": "abc-123_chunk_0",
      "text": "Machine learning is a subset of AI...",
      "file_name": "lecture_notes.png",
      "file_path": "storage/uploads/abc-123.png",
      "score": 0.91
    }
  ]
}
```

