from rich.text import Text
from textual.app import App, ComposeResult
from textual.coordinate import Coordinate
from textual.widgets import DataTable, Input, Static

from komado import Sheet


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
