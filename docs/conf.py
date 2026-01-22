# Sphinx configuration file for Agenter documentation

import sys
from pathlib import Path

# Add the project root to the path for autodoc
sys.path.insert(0, str(Path(__file__).parent.parent))

# Project information
project = "Agenter"
copyright = "2025, Moonsong Labs"
author = "Moonsong Labs"

# Get version from package
try:
    from agenter import __version__

    release = __version__
except ImportError:
    release = "0.1.0"

version = release

# Extensions
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

# Napoleon settings for Google-style docstrings
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_admonition_for_references = True
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_type_aliases = None

# Autodoc settings
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
    "show-inheritance": True,
}
autodoc_typehints = "description"
autodoc_class_signature = "separated"

# Type hints settings
typehints_defaults = "comma"
always_document_param_types = True

# MyST parser settings for markdown
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "tasklist",
]
myst_heading_anchors = 3

# Intersphinx mapping
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pydantic": ("https://docs.pydantic.dev/latest/", None),
}

# HTML output settings
html_theme = "furo"
html_title = "Agenter"
html_static_path = []
html_theme_options = {
    "light_css_variables": {
        "color-brand-primary": "#6366f1",
        "color-brand-content": "#6366f1",
    },
    "dark_css_variables": {
        "color-brand-primary": "#818cf8",
        "color-brand-content": "#818cf8",
    },
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}

# Source file settings
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# Suppress warnings for missing references to optional dependencies
nitpicky = False
