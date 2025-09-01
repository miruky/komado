"""モーションがアニメーションレベルと motion フラグを尊重することを確かめる。

テスト中のアニメーションレベルは ``full`` なので、motion=True の要素は
入場アニメーションで一時的に不透明度が下がる。ここで検証したいのは
「motion=False や reduced-motion 時には動かさず、即座に最終状態へ置く」
という、無効化の側の保証である。
"""

from textual.app import App, ComposeResult

from komado import Form, FormField, Sheet
from komado.motion import motion_allowed


class FormMotionApp(App):
    def __init__(self, motion: bool) -> None:
        super().__init__()
        self._motion = motion

    def compose(self) -> ComposeResult:
        yield Form(
            FormField("名前", "name", motion=self._motion),
            FormField("年齢", "age", motion=self._motion),
            motion=self._motion,
        )


async def test_form_without_motion_is_fully_opaque():
    app = FormMotionApp(motion=False)
    async with app.run_test():
        form = app.query_one(Form)
        for field in form.fields:
            assert field.styles.opacity == 1.0


async def test_sheet_without_motion_is_fully_opaque():
    class SheetApp(App):
        def compose(self) -> ComposeResult:
            yield Sheet(rows=4, cols=3, motion=False)

    app = SheetApp()
    async with app.run_test():
        assert app.query_one(Sheet).styles.opacity == 1.0


async def test_motion_allowed_follows_flag():
    class TwoSheets(App):
        def compose(self) -> ComposeResult:
            yield Sheet(rows=3, cols=3, motion=True, id="on")
            yield Sheet(rows=3, cols=3, motion=False, id="off")

    app = TwoSheets()
    async with app.run_test():
        assert motion_allowed(app.query_one("#on", Sheet)) is True
        assert motion_allowed(app.query_one("#off", Sheet)) is False
