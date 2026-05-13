# Smart Downloads Auto-Organizer 🚀
### AI-Powered File Intelligence with Gemini 1.5 Flash

Smart Downloads Auto-Organizer is a cutting-edge local system that transforms your messy downloads folder into a perfectly categorized workspace using state-of-the-art LLMs and semantic embeddings.

![Dashboard Preview](https://via.placeholder.com/1200x600?text=Smart+Organizer+Dashboard+Preview)

## ✨ Key Features

- **🧠 Gemini 1.5 Integration**: Uses Google's latest LLM for high-accuracy document classification.
- **🛡️ Semantic Fallback**: When offline or without an API key, the system uses **vector embeddings** (`models/embedding-001`) and cosine similarity to understand document meaning.
- **🔄 User-Correction Loop**: The system **learns from you**. If you manually reclassify a file, the system remembers that pattern for future downloads.
- **🔍 Deep Content Extraction**:
  - **OCR**: Powered by Tesseract for image-to-text.
  - **PDF & Word**: Native extraction for `.pdf` and `.docx`.
  - **Archives**: Peeks inside `.zip` and `.tar` files to identify contents.
- **🎨 Stunning UI/UX**:
  - **Modern Landing Page**: High-performance animations and glassmorphism.
  - **Control Center**: Real-time monitoring, metric tracking, and live logs.
  - **Safe Undo**: Single-click undo for any action or a complete "Undo All" rollback.
- **⚡ Real-time Monitoring**: Background watcher with file stability protection (waits for downloads to finish).

## 📂 Project Structure

```text
smart_organizer/
  classifier.py    Gemini LLM & Embedding-based logic
  database.py      SQLite audit trail & Learned patterns storage
  extractor.py     Multi-format text extraction (PDF, DOCX, OCR, Archives)
  organizer.py     Watchdog service, stability checks, and movement logic
  web.py           Flask backend & REST API
templates/
  landing.html     Animated entrance page
  index.html       Control Center Dashboard
static/
  css/landing.css  Modern landing page styles
  css/styles.css   Dashboard theme (Midnight Violet)
  js/app.js        Real-time frontend logic
```

## 🛠️ Setup

### 1. Environment Preparation
Python 3.8 or newer is required.

```bash
# Create and activate virtual environment
python -m venv myenv
myenv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. External Dependencies
- **Tesseract OCR**: Required for image extraction.
  - [Download Tesseract for Windows](https://github.com/UB-Mannheim/tesseract/wiki)
  - Set `TESSERACT_CMD` in your `.env` file to the path of `tesseract.exe`.

### 3. Configuration (`.env`)
Create a `.env` file in the root directory (see `.env.example`):

```ini
GEMINI_API_KEY=your_google_ai_key
ORGANIZER_LLM_PROVIDER=gemini
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

## 🚀 Usage

1. **Start the server**:
   ```bash
   python run.py
   ```
2. **Access the Web UI**:
   - Landing Page: `http://127.0.0.1:5000`
   - Dashboard: `http://127.0.0.1:5000/dashboard`
3. **Configure**: Select your **Watch Folder** (e.g., your Downloads folder) and click **Start Monitoring**.

## 🧠 How the AI Works

1. **Extraction**: The system reads the filename and peeks inside the file (Text, Metadata, or OCR).
2. **Generative Path**: If configured, Gemini 1.5 Flash analyzes the content and assigns a category + rationale.
3. **Semantic Path**: If the LLM is busy, the system generates a **Vector Embedding** and compares it to predefined category embeddings using **Cosine Similarity**.
4. **Learning Path**: Before any AI call, the system checks the **Learned Patterns** table to see if you've previously corrected a similar file.

## 🛡️ Safety & Reliability

- **Stability Check**: Waits for file size to stop changing before processing.
- **Atomic Moves**: Uses standard library `shutil.move` for cross-platform reliability.
- **Collision Protection**: Automatically renames files with numeric suffixes (e.g., `invoice (1).pdf`) to prevent overwriting.
- **SQLite Audit**: Every single movement is logged and can be reverted.

## 🤝 Contributing

This project was built to showcase the power of local AI in everyday utility tools. Feel free to open issues or submit PRs!

---
*Built with ❤️ by Antigravity*
