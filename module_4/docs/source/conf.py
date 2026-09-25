# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Module 4'
copyright = '2026, Carl Starvaggi'
author = 'Carl Starvaggi'
release = '1'

import os
import sys

PROJECT_ROOT = os.path.abspath("../..")
SRC_DIR = os.path.join(PROJECT_ROOT, "src")

sys.path.insert(0, SRC_DIR)
sys.path.insert(0, PROJECT_ROOT)

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = ['sphinx_rtd_theme', 'sphinx.ext.autodoc']

templates_path = ['_templates']
exclude_patterns = []



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"
html_static_path = ['_static']
