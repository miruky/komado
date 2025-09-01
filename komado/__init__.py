"""Textual向けのTUI部品集。フォームバリデーションと表計算ウィジェットを提供する。"""

from .form import CrossRule, Form, FormField
from .formula import Engine, FormulaError, parse_ref, ref_to_a1
from .sheet import Sheet

__version__ = "0.1.0"

__all__ = [
    "CrossRule",
    "Engine",
    "Form",
    "FormField",
    "FormulaError",
    "Sheet",
    "__version__",
    "parse_ref",
    "ref_to_a1",
]
