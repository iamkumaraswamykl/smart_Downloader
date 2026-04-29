# Smart Downloads Auto-Organizer Using NLP-Driven File Classification

Smart Downloads Auto-Organizer is a local Python system that watches a folder in real time, extracts file content, classifies downloads semantically, and moves them into clean category folders. It includes a Flask dashboard for folder selection, live status, audit history, undo, and manual reclassification.

## What it does

- Monitors a selected folder in real time with `watchdog`.
- Waits until newly downloaded files are stable before processing.
- Extracts text from PDFs with `pdfplumber` first and `PyPDF2` as a fallback.
- Extracts image text with OCR using `pytesseract` and `Pillow`.
- Reads plain text and code-like files directly.
- Classifies files by content using a built-in semantic classifier.
- Optionally delegates classification to an OpenAI-compatible LLM when configured.
- Moves files into predefined category folders.
- Logs every action to SQLite and `logs/organizer.log`.
- Handles corrupted, unsupported, and unreadable files by using `Uncategorized`.
- Supports undo and manual reclassification from the dashboard.

## Project structure

```text
smart_organizer/
  classifier.py    Local semantic classifier and optional LLM hook
  database.py      SQLite audit trail
  extractor.py     PDF, OCR image, and text extraction
  organizer.py     Watchdog service, stability checks, moves, undo
  web.py           Flask dashboard and JSON API
templates/
  index.html       Dashboard UI
static/
  css/styles.css   Frontend styling
  js/app.js        Dashboard behavior
tests/
  test_classifier.py
  test_paths.py
```

## Setup

Python 3.8 or newer is required.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

For OCR, install Tesseract separately:

- Windows: install Tesseract OCR and set `TESSERACT_CMD` in `.env` or your shell.
- macOS: `brew install tesseract`
- Linux: install the `tesseract-ocr` package from your distribution.

`python-magic` may need platform support. On Windows, if `python-magic` cannot locate libmagic, install `python-magic-bin` instead.

## Optional LLM classification

The system works without an API key. To use an OpenAI LLM, set:

```bash
set ORGANIZER_LLM_PROVIDER=openai
set OPENAI_API_KEY=your_key_here
set OPENAI_MODEL=gpt-4o-mini
```

When the LLM is unavailable or errors, the local classifier is used automatically.

## Run

```bash
python run.py
```

Open:

```text
http://127.0.0.1:5000
```

Use the dashboard to select the watch folder and destination root, then start monitoring. If the destination root is blank, the app creates an `Organized` folder inside the watched folder.

## Categories

Default categories are:

- Academic
- Finance
- Legal
- Work
- Personal
- Documents
- Code
- Images
- Media
- Archives
- Uncategorized

You can adjust category descriptions, folder names, and semantic keywords in `smart_organizer/config.py`.

## Safety behavior

- Temporary browser download files such as `.crdownload`, `.part`, and `.tmp` are ignored.
- The organizer waits for file size stability and successful read access before moving a file.
- Files are never overwritten. Existing destination names receive a numeric suffix.
- Every movement is stored in SQLite so it can be undone from the dashboard.
- Unsupported or unreadable files are logged and routed to `Uncategorized` when possible.

## Tests

```bash
pytest
```

