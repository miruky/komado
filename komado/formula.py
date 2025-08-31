"""表計算ウィジェットの数式エンジン。

セル参照(A1形式)・四則演算・集計関数を持つ小さな式言語を評価する。
Textualに依存しないため、ウィジェットと切り離して単体でテストできる。
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

Ref = tuple[int, int]
"""セル座標。(行, 列) の0始まりタプル。A1 は (0, 0)。"""


class FormulaError(Exception):
    """数式の解析・評価の失敗。code はセルに表示する短い識別子。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_REF_PATTERN = re.compile(r"^([A-Z]+)([1-9][0-9]*)$")


def parse_ref(text: str) -> Ref:
    """A1形式の参照を (行, 列) に変換する。不正な形式は FormulaError。"""
    m = _REF_PATTERN.match(text.upper())
    if m is None:
        raise FormulaError("#REF!", f"セル参照として解釈できない: {text}")
    letters, digits = m.groups()
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - ord("A") + 1)
    return int(digits) - 1, col - 1


def ref_to_a1(ref: Ref) -> str:
    """(行, 列) をA1形式の文字列に戻す。"""
    row, col = ref
    letters = ""
    col += 1
    while col > 0:
        col, rem = divmod(col - 1, 26)
        letters = chr(ord("A") + rem) + letters
    return f"{letters}{row + 1}"


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str


_TOKEN_RE = re.compile(
    r"""
    (?P<number>[0-9]+(?:\.[0-9]+)?)
  | (?P<range>[A-Za-z]+[1-9][0-9]*:[A-Za-z]+[1-9][0-9]*)
  | (?P<name>[A-Za-z]+[0-9]*)
  | (?P<op>[+\-*/(),])
  | (?P<ws>\s+)
    """,
    re.VERBOSE,
)


def _tokenize(source: str) -> Iterator[_Token]:
    pos = 0
    while pos < len(source):
        m = _TOKEN_RE.match(source, pos)
        if m is None:
            raise FormulaError("#ERROR!", f"解釈できない文字: {source[pos]!r}")
        pos = m.end()
        kind = m.lastgroup or ""
        if kind != "ws":
            yield _Token(kind, m.group())


# AST ノード。タプルで表現する:
#   ("num", float) / ("ref", Ref) / ("range", Ref, Ref)
#   ("bin", op, left, right) / ("neg", operand) / ("call", name, [args])
Node = tuple


class _Parser:
    """再帰下降パーサ。優先順位は 単項マイナス > 乗除 > 加減。"""

    def __init__(self, source: str) -> None:
        self._tokens = list(_tokenize(source))
        self._pos = 0

    def parse(self) -> Node:
        node = self._expr()
        if self._pos < len(self._tokens):
            raise FormulaError("#ERROR!", f"式の途中で終わっている: {self._peek().text!r} 以降")
        return node

    def _peek(self) -> _Token:
        return self._tokens[self._pos]

    def _at_end(self) -> bool:
        return self._pos >= len(self._tokens)

    def _take(self) -> _Token:
        if self._at_end():
            raise FormulaError("#ERROR!", "式が途中で終わっている")
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _match_op(self, *ops: str) -> str | None:
        if not self._at_end() and self._peek().kind == "op" and self._peek().text in ops:
            return self._take().text
        return None

    def _expr(self) -> Node:
        node = self._term()
        while (op := self._match_op("+", "-")) is not None:
            node = ("bin", op, node, self._term())
        return node

    def _term(self) -> Node:
        node = self._unary()
        while (op := self._match_op("*", "/")) is not None:
            node = ("bin", op, node, self._unary())
        return node

    def _unary(self) -> Node:
        if self._match_op("-") is not None:
            return ("neg", self._unary())
        return self._primary()

    def _primary(self) -> Node:
        token = self._take()
        if token.kind == "number":
            return ("num", float(token.text))
        if token.kind == "range":
            start, end = token.text.split(":")
            return ("range", parse_ref(start), parse_ref(end))
        if token.kind == "name":
            if self._match_op("(") is not None:
                return self._call(token.text.upper())
            return ("ref", parse_ref(token.text))
        if token.kind == "op" and token.text == "(":
            node = self._expr()
            if self._match_op(")") is None:
                raise FormulaError("#ERROR!", "閉じ括弧がない")
            return node
        raise FormulaError("#ERROR!", f"予期しないトークン: {token.text!r}")

    def _call(self, name: str) -> Node:
        args: list[Node] = []
        if self._match_op(")") is not None:
            return ("call", name, args)
        args.append(self._expr())
        while self._match_op(",") is not None:
            args.append(self._expr())
        if self._match_op(")") is None:
            raise FormulaError("#ERROR!", f"{name} の閉じ括弧がない")
        return ("call", name, args)


def _fn_round(values: list[float]) -> float:
    if len(values) == 1:
        return float(round(values[0]))
    if len(values) == 2:
        return round(values[0], int(values[1]))
    raise FormulaError("#ERROR!", "ROUND の引数は1個か2個")


_AGGREGATES: dict[str, Callable[[list[float]], float]] = {
    "SUM": lambda xs: sum(xs),
    "AVERAGE": lambda xs: sum(xs) / len(xs),
    "MIN": min,
    "MAX": max,
    "COUNT": lambda xs: float(len(xs)),
}

_SCALARS: dict[str, Callable[[list[float]], float]] = {
    "ABS": lambda xs: abs(xs[0]),
    "ROUND": _fn_round,
}

FUNCTION_NAMES = tuple(sorted(_AGGREGATES | _SCALARS))


class Engine:
    """セルの生テキストを保持し、数式を依存解決つきで評価する。

    `=` で始まるテキストを数式、数値に見えるテキストを数値、
    それ以外を文字列として扱う。評価結果はセット時に無効化される
    メモに保持し、循環参照は訪問中セルの検出で #CYCLE! にする。
    """

    def __init__(self) -> None:
        self._raw: dict[Ref, str] = {}
        self._memo: dict[Ref, float | str] = {}
        self._visiting: set[Ref] = set()

    def set_cell(self, ref: Ref | str, text: str) -> None:
        ref = parse_ref(ref) if isinstance(ref, str) else ref
        if text.strip() == "":
            self._raw.pop(ref, None)
        else:
            self._raw[ref] = text
        self._memo.clear()

    def raw(self, ref: Ref | str) -> str:
        ref = parse_ref(ref) if isinstance(ref, str) else ref
        return self._raw.get(ref, "")

    def refs(self) -> set[Ref]:
        """値を持つセルの座標一覧。"""
        return set(self._raw)

    def value(self, ref: Ref | str) -> float | str:
        """セルの評価値。空セルは空文字列、エラーはエラーコード文字列。"""
        ref = parse_ref(ref) if isinstance(ref, str) else ref
        if ref in self._memo:
            return self._memo[ref]
        try:
            result = self._evaluate_cell(ref)
        except FormulaError as error:
            result = error.code
        finally:
            self._visiting.discard(ref)
        self._memo[ref] = result
        return result

    def display(self, ref: Ref | str) -> str:
        """セルの表示文字列。整数になる値は小数点を付けない。"""
        value = self.value(ref)
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:g}"
        return value

    def _evaluate_cell(self, ref: Ref) -> float | str:
        if ref in self._visiting:
            raise FormulaError("#CYCLE!", f"{ref_to_a1(ref)} が自分自身に依存している")
        text = self._raw.get(ref)
        if text is None:
            return ""
        if text.startswith("="):
            self._visiting.add(ref)
            try:
                return self._eval_node(_Parser(text[1:]).parse())
            finally:
                self._visiting.discard(ref)
        try:
            return float(text)
        except ValueError:
            return text

    def _number_at(self, ref: Ref) -> float:
        value = self.value(ref)
        if isinstance(value, float):
            return value
        if value == "":
            return 0.0
        if value.startswith("#"):
            raise FormulaError(value, f"{ref_to_a1(ref)} がエラー値")
        raise FormulaError("#VALUE!", f"{ref_to_a1(ref)} は数値でない: {value!r}")

    def _range_numbers(self, start: Ref, end: Ref) -> list[float]:
        rows = range(min(start[0], end[0]), max(start[0], end[0]) + 1)
        cols = range(min(start[1], end[1]), max(start[1], end[1]) + 1)
        numbers: list[float] = []
        for row in rows:
            for col in cols:
                value = self.value((row, col))
                if isinstance(value, float):
                    numbers.append(value)
                elif value.startswith("#"):
                    raise FormulaError(value, f"{ref_to_a1((row, col))} がエラー値")
        return numbers

    def _eval_node(self, node: Node) -> float:
        kind = node[0]
        if kind == "num":
            return node[1]
        if kind == "ref":
            return self._number_at(node[1])
        if kind == "neg":
            return -self._eval_node(node[1])
        if kind == "bin":
            return self._eval_bin(node[1], node[2], node[3])
        if kind == "call":
            return self._eval_call(node[1], node[2])
        if kind == "range":
            raise FormulaError("#ERROR!", "範囲は関数の引数にだけ書ける")
        raise FormulaError("#ERROR!", f"未知のノード: {kind}")

    def _eval_bin(self, op: str, left: Node, right: Node) -> float:
        a = self._eval_node(left)
        b = self._eval_node(right)
        if op == "+":
            return a + b
        if op == "-":
            return a - b
        if op == "*":
            return a * b
        if b == 0:
            raise FormulaError("#DIV/0!", "0で割った")
        return a / b

    def _eval_call(self, name: str, args: list[Node]) -> float:
        if name in _AGGREGATES:
            numbers: list[float] = []
            for arg in args:
                if arg[0] == "range":
                    numbers.extend(self._range_numbers(arg[1], arg[2]))
                else:
                    numbers.append(self._eval_node(arg))
            if not numbers:
                raise FormulaError("#ERROR!", f"{name} に渡す値がない")
            return _AGGREGATES[name](numbers)
        if name in _SCALARS:
            if not args:
                raise FormulaError("#ERROR!", f"{name} に引数がない")
            return _SCALARS[name]([self._eval_node(arg) for arg in args])
        raise FormulaError("#NAME?", f"未知の関数: {name}")
