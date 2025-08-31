"""表計算ウィジェット。

`DataTable` をグリッド表示に使い、編集は上部の数式バーで行う。
セルの値と数式の評価は `komado.formula.Engine` に委ねる。
"""

from __future__ import annotations

import csv
import io
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.message import Message
from textual.widgets import DataTable, Input, Static

from .formula import Engine, Ref, ref_to_a1


class Sheet(Vertical):
    """数式バー付きの編集可能なグリッド。

    矢印キーでセルを移動し、Enterで数式バーにフォーカスして編集する。
    `=SUM(A1:A5)` のような数式は確定時に評価され、依存セルの表示も
    まとめて更新される。
    """

    BINDINGS: ClassVar = [
        Binding("backspace,delete", "clear_cell", "セルを消去", show=True),
        Binding("escape", "focus_grid", "グリッドへ戻る", show=False),
    ]

    DEFAULT_CSS = """
    Sheet {
        height: auto;
    }
    Sheet > .komado-sheet-bar {
        margin-bottom: 0;
    }
    Sheet > DataTable {
        height: auto;
        max-height: 100%;
    }
    Sheet > .komado-sheet-status {
        color: $text-muted;
        height: 1;
    }
    """

    class CellChanged(Message):
        """セルの確定編集。raw は入力テキスト、display は評価後の表示文字列。"""

        def __init__(self, sheet: Sheet, ref: Ref, raw: str, display: str) -> None:
            super().__init__()
            self.sheet = sheet
            self.ref = ref
            self.raw = raw
            self.display = display

    def __init__(
        self,
        rows: int = 20,
        cols: int = 8,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.rows = rows
        self.cols = cols
        self.engine = Engine()
        self._bar = Input(placeholder="値か =数式 を入力", classes="komado-sheet-bar")
        self._table = DataTable(cursor_type="cell", zebra_stripes=True)
        self._status = Static("", classes="komado-sheet-status")

    def compose(self) -> ComposeResult:
        yield self._bar
        yield self._table
        yield self._status

    def on_mount(self) -> None:
        self._table.add_columns(*(ref_to_a1((0, c))[:-1] for c in range(self.cols)))
        for row in range(self.rows):
            self._table.add_row(*[""] * self.cols, label=str(row + 1))
        self._refresh_all()
        self._sync_bar()
        self._table.focus()

    @property
    def cursor_ref(self) -> Ref:
        coordinate = self._table.cursor_coordinate
        return (coordinate.row, coordinate.column)

    def set_cell(self, ref: Ref | str, text: str) -> None:
        """APIからの書き込み。マウント済みなら表示も更新する。"""
        self.engine.set_cell(ref, text)
        if self._table.row_count:
            self._refresh_all()
            self._sync_bar()

    def load_rows(self, rows: list[list[str]], *, origin: Ref = (0, 0)) -> None:
        """2次元リストを origin を左上としてまとめて流し込む。"""
        for dr, row in enumerate(rows):
            for dc, text in enumerate(row):
                self.engine.set_cell((origin[0] + dr, origin[1] + dc), text)
        if self._table.row_count:
            self._refresh_all()
            self._sync_bar()

    def to_csv(self) -> str:
        """評価後の値をCSVにする。末尾の空行・空列は含めない。"""
        refs = self.engine.refs()
        if not refs:
            return ""
        last_row = max(r for r, _ in refs)
        last_col = max(c for _, c in refs)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in range(last_row + 1):
            writer.writerow([self.engine.display((row, col)) for col in range(last_col + 1)])
        return buffer.getvalue()

    def action_clear_cell(self) -> None:
        if self._table.has_focus:
            self._commit(self.cursor_ref, "")

    def action_focus_grid(self) -> None:
        self._table.focus()

    def _commit(self, ref: Ref, text: str) -> None:
        self.engine.set_cell(ref, text)
        self._refresh_all()
        self._sync_bar()
        self.post_message(self.CellChanged(self, ref, text, self.engine.display(ref)))

    def _refresh_all(self) -> None:
        """数式の依存先を個別追跡せず、毎回全セルを再描画する。

        グリッドは高々数百セルで、Engine側のメモ化により再計算は
        セルあたり1回で済むため、これで十分速い。
        """
        for row in range(self.rows):
            for col in range(self.cols):
                self._table.update_cell_at(
                    Coordinate(row, col),
                    self.engine.display((row, col)),
                    update_width=True,
                )

    def _sync_bar(self) -> None:
        ref = self.cursor_ref
        self._bar.value = self.engine.raw(ref)
        value = self.engine.display(ref)
        suffix = f" = {value}" if self.engine.raw(ref).startswith("=") else ""
        self._status.update(f"{ref_to_a1(ref)}{suffix}")

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        event.stop()
        self._sync_bar()

    def on_data_table_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Enterかクリックで選択したセルを数式バーで編集する。"""
        event.stop()
        self._bar.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()
        ref = self.cursor_ref
        self._commit(ref, event.value)
        next_row = min(ref[0] + 1, self.rows - 1)
        self._table.cursor_coordinate = Coordinate(next_row, ref[1])
        self._table.focus()
