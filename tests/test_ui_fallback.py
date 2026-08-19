import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from ui import HudCanvas


def test_missing_face_file_does_not_emit_warning(capsys):
    app = QApplication.instance() or QApplication([])
    canvas = HudCanvas("missing-face.png")
    assert canvas._face_px is None
    captured = capsys.readouterr()
    assert "Could not load face image" not in captured.out
    app.quit()
