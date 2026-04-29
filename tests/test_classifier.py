from pathlib import Path

from smart_organizer.classifier import SemanticClassifier


def test_academic_classification_from_content():
    classifier = SemanticClassifier()
    result = classifier.classify(
        "This research paper contains an abstract, citations, references and a dataset.",
        Path("paper.pdf"),
        "application/pdf",
    )
    assert result.category == "Academic"
    assert result.confidence > 0.4


def test_finance_classification_from_content():
    classifier = SemanticClassifier()
    result = classifier.classify(
        "Invoice amount due with payment transaction and bank account statement.",
        Path("download.txt"),
        "text/plain",
    )
    assert result.category == "Finance"


def test_image_fallback_without_ocr_text():
    classifier = SemanticClassifier()
    result = classifier.classify("", Path("scan.png"), "image/png")
    assert result.category == "Images"

