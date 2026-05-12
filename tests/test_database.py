from smart_organizer.database import OrganizerDatabase


def _payload(file_name, category="Documents", status="moved"):
    return {
        "original_path": f"/tmp/{file_name}",
        "current_path": f"/tmp/Organized/{category}/{file_name}",
        "destination_path": f"/tmp/Organized/{category}/{file_name}",
        "file_name": file_name,
        "category": category,
        "confidence": 0.8,
        "method": "test",
        "mime_type": "text/plain",
        "extractor": "text",
        "status": status,
        "error": "boom" if status == "error" else "",
        "extracted_preview": "",
        "moved_at": None,
    }


def test_summary_counts_processed_errors_and_categories(tmp_path):
    db = OrganizerDatabase(tmp_path / "organizer.db")
    db.record_action(_payload("notes.txt", "Academic"))
    db.record_action(_payload("invoice.txt", "Finance"))
    db.record_action(_payload("old.txt", "Personal", "undone"))
    db.record_error("/tmp/bad.pdf", "bad.pdf", "Unreadable")

    summary = db.summary()

    assert summary["total_actions"] == 4
    assert summary["processed"] == 2
    assert summary["errors"] == 1
    assert summary["category_counts"] == [
        {"category": "Academic", "count": 1},
        {"category": "Finance", "count": 1},
    ]
    assert summary["latest"]["file_name"] == "bad.pdf"
