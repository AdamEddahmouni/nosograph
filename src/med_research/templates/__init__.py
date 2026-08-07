"""Jinja2 template infrastructure for HTML report generation.

Provides a pre-configured Jinja2 environment with auto-escaping
enabled for .html files, loaded from the templates/ directory.
"""

import contextlib
import os

import jinja2
from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATE_DIR = os.path.dirname(os.path.abspath(__file__))

env = Environment(
    loader=FileSystemLoader(_TEMPLATE_DIR),
    autoescape=select_autoescape(["html"]),
)

# Preload every template at import time so report modules never read template
# files lazily at render time. Tests that patch ``builtins.open`` (to capture
# report output) would otherwise intercept the loader's file reads and render
# empty templates. With the cache warm, ``get_template`` never hits the loader.
# Only .html files are templates — exclude stray files (e.g. .pyc artifacts).
# Templates that fail to compile are skipped so a malformed file can't break
# unrelated report imports.
for _name in env.list_templates():
    if _name.endswith(".html"):
        with contextlib.suppress(jinja2.TemplateSyntaxError, jinja2.TemplateError):
            env.get_template(_name)
