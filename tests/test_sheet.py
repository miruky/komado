import pytest
from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static

from komado import FormulaError, Sheet


class SheetApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.changes: list[tuple[tuple[int, int], str, str]] = []

    def compose(self) -> ComposeResult:
        yield Sheet(rows=6, cols=4)

    def on_sheet_cell_changed(self, event: Sheet.CellChanged) -> None:
        self.changes.append((event.ref, event.raw, event.display))


def cell_text(sheet: Sheet, row: int, col: int) -> str:
    return str(sheet.query_one(DataTable).get_cell_at(Coordinate(row, col)))


async def test_set_cell_updates_grid():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "100")
        assert cell_text(sheet, 0, 0) == "100"


async def test_formula_shows_computed_value():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "2")
        sheet.set_cell("A2", "3")
        sheet.set_cell("B1", "=SUM(A1:A2)*10")
        assert cell_text(sheet, 0, 1) == "50"


async def test_load_rows():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.load_rows([["1", "2"], ["3", "=A1+B1+A2"]])
        assert cell_text(sheet, 1, 1) == "6"


async def test_edit_via_formula_bar():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("enter")
        assert sheet.query_one(Input).has_focus
        await pilot.press(*"=6*7", "enter")
        assert cell_text(sheet, 0, 0) == "42"
        assert app.changes == [((0, 0), "=6*7", "42")]


async def test_cursor_advances_after_commit():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("enter", *"10", "enter")
        assert sheet.cursor_ref == (1, 0)
        table = sheet.query_one(DataTable)
        assert table.has_focus


async def test_dependents_update_after_edit():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        sheet.set_cell("B1", "=A1*2")
        await pilot.press("enter", *"21", "enter")
        assert cell_text(sheet, 0, 1) == "42"


async def test_delete_clears_cell():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "9")
        await pilot.press("delete")
        assert cell_text(sheet, 0, 0) == ""
        assert sheet.engine.raw("A1") == ""


async def test_formula_bar_shows_raw_text():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "=1+1")
        await pilot.pause()
        assert sheet.query_one(Input).value == "=1+1"


async def test_error_code_is_displayed():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "=1/0")
        assert cell_text(sheet, 0, 0) == "#DIV/0!"


async def test_to_csv_contains_computed_values():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.load_rows([["品名", "数"], ["りんご", "3"], ["合計", "=SUM(B2:B2)"]])
        lines = sheet.to_csv().strip().splitlines()
        assert lines == ["品名,数", "りんご,3", "合計,3"]


async def test_to_csv_empty_sheet():
    app = SheetApp()
    async with app.run_test():
        assert app.query_one(Sheet).to_csv() == ""


def cell_renderable(sheet: Sheet, row: int, col: int) -> Text:
    cell = sheet.query_one(DataTable).get_cell_at(Coordinate(row, col))
    assert isinstance(cell, Text)
    return cell


async def test_number_cell_is_right_aligned():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "100")
        assert cell_renderable(sheet, 0, 0).justify == "right"


async def test_text_cell_is_not_right_aligned():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "費目")
        assert cell_renderable(sheet, 0, 0).justify != "right"


async def test_error_cell_is_red_but_plain_text_intact():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "=1/0")
        cell = cell_renderable(sheet, 0, 0)
        assert str(cell) == "#DIV/0!"
        assert "red" in str(cell.style)


async def test_namebox_tracks_cursor():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("right", "down")
        namebox = sheet.query_one(".komado-sheet-namebox", Static)
        assert str(namebox.render()) == "B2"


async def test_undo_and_redo_roundtrip():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("enter", *"10", "enter")  # A1=10
        await pilot.press("enter", *"20", "enter")  # A2=20
        await pilot.press("ctrl+z")
        assert cell_text(sheet, 1, 0) == ""
        assert sheet.cursor_ref == (1, 0)
        await pilot.press("ctrl+z")
        assert cell_text(sheet, 0, 0) == ""
        await pilot.press("ctrl+y")
        assert cell_text(sheet, 0, 0) == "10"


async def test_redo_is_dropped_after_new_edit():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("enter", *"10", "enter")
        await pilot.press("ctrl+z")
        await pilot.press("enter", *"99", "enter")  # 新しい編集でredo破棄
        await pilot.press("ctrl+y")
        assert cell_text(sheet, 0, 0) == "99"


async def test_load_csv_replaces_content():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("D4", "残骸")
        sheet.load_csv("品,数\nりんご,3\n合計,=B2\n")
        assert cell_text(sheet, 0, 0) == "品"
        assert cell_text(sheet, 2, 1) == "3"
        assert cell_text(sheet, 3, 3) == ""  # 既存の D4 は消える


async def test_load_csv_clears_undo_history():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("enter", *"5", "enter")
        sheet.load_csv("a,b\n1,2\n")
        await pilot.press("ctrl+z")  # 履歴が消えているので何も起きない
        assert cell_text(sheet, 0, 0) == "a"


async def test_clear_empties_sheet():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.load_rows([["1", "2"], ["3", "4"]])
        sheet.clear()
        assert cell_text(sheet, 0, 0) == ""
        assert sheet.engine.refs() == set()


async def test_undo_redo_at_boundaries_are_noops():
    app = SheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        await pilot.press("ctrl+z")
        await pilot.press("ctrl+y")
        assert cell_text(sheet, 0, 0) == ""


async def test_load_csv_handles_ragged_and_empty_rows():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.load_csv("a,b,c\n1\n\n4,5\n")
        assert cell_text(sheet, 0, 0) == "a"
        assert cell_text(sheet, 1, 0) == "1"
        assert cell_text(sheet, 1, 1) == ""
        assert cell_text(sheet, 3, 1) == "5"


async def test_load_csv_empty_clears_sheet():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "x")
        sheet.load_csv("")
        assert cell_text(sheet, 0, 0) == ""


async def test_set_cell_with_invalid_ref_raises():
    app = SheetApp()
    async with app.run_test():
        sheet = app.query_one(Sheet)
        with pytest.raises(FormulaError):
            sheet.set_cell("A0", "5")


class BigSheetApp(App):
    def compose(self) -> ComposeResult:
        yield Sheet(rows=30, cols=12, motion=False)


async def test_large_sheet_computes_far_corner():
    app = BigSheetApp()
    async with app.run_test() as pilot:
        sheet = app.query_one(Sheet)
        sheet.set_cell("A1", "1")
        sheet.set_cell("L30", "=A1+1")
        await pilot.pause()
        assert cell_text(sheet, 29, 11) == "2"
