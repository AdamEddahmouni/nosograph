"""Jinja2 template infrastructure for HTML report generation.

Provides a pre-configured Jinja2 environment with auto-escaping
enabled for .html files, loaded from the templates/ directory.
"""

import os

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))

env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)
