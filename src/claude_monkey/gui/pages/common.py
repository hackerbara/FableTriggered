"""Small widgets/helpers shared by settings window pages."""

from __future__ import annotations

import re

from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

_SLUG_RUN = re.compile(r"[^a-z0-9]+")


class Banner(QWidget):
    """Dismissible inline error banner, one per settings page."""

    def __init__(self) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setStyleSheet("color: #a00; font-weight: bold;")
        layout.addWidget(self.label, 1)
        self.dismiss_button = QPushButton("Dismiss")
        self.dismiss_button.clicked.connect(self.hide)
        layout.addWidget(self.dismiss_button)
        self.hide()

    def show_message(self, message: str) -> None:
        self.label.setText(message)
        self.show()


def slugify(text: str) -> str:
    """Turn arbitrary text (typically a filename stem) into an id-safe slug.

    Lowercases, collapses any run of non `[a-z0-9]` characters into a single
    hyphen, and strips leading/trailing hyphens. Falls back to "prompt" for
    input that has no alphanumeric characters at all, so a slugged id is
    never empty.
    """
    slug = _SLUG_RUN.sub("-", text.strip().lower()).strip("-")
    return slug or "prompt"
