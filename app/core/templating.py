"""Shared Jinja2 templates instance.
Any router that serves HTML uses this `templates` object, so partials
(header, footer, cart drawer) are consistent across all pages.
"""
from pathlib import Path
from fastapi.templating import Jinja2Templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))