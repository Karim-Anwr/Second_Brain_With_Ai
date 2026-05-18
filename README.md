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
# Ubuntu / Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract

# Windows
# Download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki
```

### 2. Clone the project

```bash
git clone https://github.com/your-username/second-brain.git
cd second-brain
```

### 3. Create virtual environment

```bash
python3 -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows
venv\Scripts\activate
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
uvicorn app.main:app --reload
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
  "document_id": "abc-123",
  "file_name": "screenshot.png",
  "file_type": "image",
  "chunks_stored": 3,
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

