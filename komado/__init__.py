"""Textual向けのTUI部品集。フォームバリデーションと表計算ウィジェットを提供する。"""

from .form import CrossRule, Field, Form, FormField, SelectField, SwitchField
from .formula import Engine, FormulaError, parse_ref, ref_to_a1
from .sheet import Sheet

__version__ = "0.2.0"

__all__ = [
    "CrossRule",
    "Engine",
    "Field",
    "Form",
    "FormField",
    "FormulaError",
    "SelectField",
    "Sheet",
    "SwitchField",
    "__version__",
    "parse_ref",
    "ref_to_a1",
]
