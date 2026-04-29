from pathlib import Path
import os


APP_NAME = "Smart Downloads Auto-Organizer"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DEFAULT_DB_PATH = Path(os.getenv("ORGANIZER_DB_PATH", DATA_DIR / "organizer.db"))
DEFAULT_LOG_PATH = Path(os.getenv("ORGANIZER_LOG_PATH", LOG_DIR / "organizer.log"))

DEFAULT_CATEGORIES = {
    "Academic": {
        "folder": "Academic",
        "description": "Research papers, assignments, notes, syllabi, certificates, lecture material.",
        "keywords": [
            "research", "journal", "conference", "abstract", "citation", "references",
            "thesis", "assignment", "lecture", "syllabus", "course", "exam", "university",
            "college", "paper", "study", "dataset", "professor", "semester", "grade",
            "transcript", "certificate", "workshop", "publication", "doi",
        ],
    },
    "Finance": {
        "folder": "Finance",
        "description": "Invoices, receipts, statements, tax documents, banking and payments.",
        "keywords": [
            "invoice", "receipt", "payment", "transaction", "balance", "statement",
            "account", "bank", "tax", "gst", "salary", "bill", "amount due",
            "credit", "debit", "upi", "refund", "quotation", "purchase order",
            "ledger", "financial", "insurance premium",
        ],
    },
    "Legal": {
        "folder": "Legal",
        "description": "Contracts, agreements, policies, legal notices and compliance files.",
        "keywords": [
            "contract", "agreement", "terms", "conditions", "privacy policy", "legal",
            "notice", "affidavit", "compliance", "clause", "warranty", "license",
            "memorandum", "nda", "signature", "court", "liability", "jurisdiction",
        ],
    },
    "Work": {
        "folder": "Work",
        "description": "Office material, proposals, business reports, meeting notes and resumes.",
        "keywords": [
            "project", "proposal", "meeting", "minutes", "client", "deadline",
            "roadmap", "business", "report", "dashboard", "resume", "curriculum vitae",
            "cover letter", "presentation", "team", "stakeholder", "deliverable",
            "sprint", "okr", "kpi", "requirements",
        ],
    },
    "Personal": {
        "folder": "Personal",
        "description": "Personal IDs, travel documents, health records, letters and family files.",
        "keywords": [
            "passport", "aadhaar", "pan", "driver license", "personal", "family",
            "medical", "prescription", "doctor", "appointment", "travel", "ticket",
            "boarding pass", "itinerary", "wedding", "birth", "address", "identity",
            "health", "vaccination",
        ],
    },
    "Documents": {
        "folder": "Documents",
        "description": "General text-heavy files that do not strongly match another domain.",
        "keywords": [
            "document", "manual", "guide", "instructions", "overview", "notes",
            "draft", "summary", "form", "application", "letter", "template",
            "checklist", "readme", "reference",
        ],
    },
    "Code": {
        "folder": "Code",
        "description": "Source code, scripts, configuration files and technical snippets.",
        "keywords": [
            "def ", "class ", "import ", "function", "const ", "let ", "var ",
            "public static", "dockerfile", "requirements.txt", "package.json",
            "api_key", "endpoint", "traceback", "exception", "schema", "migration",
        ],
    },
    "Images": {
        "folder": "Images",
        "description": "Photos, scans, screenshots and image-only files.",
        "keywords": [
            "screenshot", "photo", "image", "camera", "pixel", "resolution",
            "scan", "ocr", "portrait", "landscape",
        ],
    },
    "Media": {
        "folder": "Media",
        "description": "Audio and video downloads.",
        "keywords": [
            "audio", "video", "mp3", "mp4", "wav", "mpeg", "subtitle", "duration",
            "recording", "codec",
        ],
    },
    "Archives": {
        "folder": "Archives",
        "description": "Compressed bundles and backups.",
        "keywords": [
            "zip", "rar", "7z", "tar", "archive", "backup", "compressed",
            "bundle", "export",
        ],
    },
    "Uncategorized": {
        "folder": "Uncategorized",
        "description": "Fallback category for unsupported, unreadable or ambiguous files.",
        "keywords": [],
    },
}


TEMP_EXTENSIONS = {
    ".crdownload",
    ".download",
    ".part",
    ".tmp",
    ".temp",
}


TEXT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".tsv",
    ".json",
    ".xml",
    ".yaml",
    ".yml",
    ".log",
    ".ini",
    ".cfg",
    ".py",
    ".js",
    ".ts",
    ".html",
    ".css",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".go",
    ".rs",
    ".sql",
}


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff", ".tif", ".webp"}
PDF_EXTENSIONS = {".pdf"}
ARCHIVE_EXTENSIONS = {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"}
MEDIA_EXTENSIONS = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".mp4", ".mov", ".avi", ".mkv", ".webm"}

