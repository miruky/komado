"""komadoの動作を一覧できるデモアプリ。`python -m komado.demo` で起動する。"""

from __future__ import annotations

import re

from textual.app import App, ComposeResult
from textual.containers import VerticalScroll
from textual.validation import Integer, Regex
from textual.widgets import Footer, Header, Static, TabbedContent, TabPane

from .form import Form, FormField, SelectField, SwitchField
from .sheet import Sheet
from .theme import DEFAULT_THEME, register_themes

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _passwords_match(values: dict[str, str]) -> str | None:
    if values["password"] != values["confirm"]:
        return "パスワードが一致していません"
    return None


class DemoApp(App):
    """フォームとシートをタブで切り替えるショーケース。"""

    TITLE = "komado デモ"
    CSS = """
    #form-result {
        margin: 1 2;
        color: $text-success;
        height: auto;
    }
    TabPane {
        padding: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent():
            with TabPane("フォーム", id="tab-form"), VerticalScroll():
                yield Form(
                    FormField("名前", "name", required=True, placeholder="山田太郎"),
                    FormField(
                        "メールアドレス",
                        "email",
                        required=True,
                        validators=[
                            Regex(_EMAIL_RE, failure_description="メールアドレスの形式が不正です")
                        ],
                        placeholder="taro@example.com",
                    ),
                    FormField(
                        "年齢",
                        "age",
                        validators=[
                            Integer(
                                minimum=0,
                                maximum=130,
                                failure_description="0から130の整数で入力してください",
                            )
                        ],
                    ),
                    SelectField("プラン", "plan", ["無料", "有料", "法人"], required=True),
                    SwitchField("メール通知を受け取る", "notify", value=True),
                    FormField("パスワード", "password", required=True, password=True),
                    FormField("パスワード(確認)", "confirm", required=True, password=True),
                    rules=[_passwords_match],
                    submit_label="登録",
                )
                yield Static("", id="form-result")
            with TabPane("シート", id="tab-sheet"):
                yield Sheet(rows=12, cols=6)
        yield Footer()

    def on_mount(self) -> None:
        # 既定の彩度の高い配色ではなく、komadoの落ち着いたテーマで見せる。
        register_themes(self)
        self.theme = DEFAULT_THEME
        sheet = self.query_one(Sheet)
        sheet.load_rows(
            [
                ["費目", "4月", "5月", "6月"],
                ["家賃", "82000", "82000", "82000"],
                ["食費", "41200", "38900", "44510"],
                ["光熱費", "9800", "8200", "7600"],
                ["合計", "=SUM(B2:B4)", "=SUM(C2:C4)", "=SUM(D2:D4)"],
                ["平均", "=AVERAGE(B2:B4)", "=AVERAGE(C2:C4)", "=AVERAGE(D2:D4)"],
                ["予算内", "=IF(B5<=130000,1,0)", "=IF(C5<=130000,1,0)", "=IF(D5<=130000,1,0)"],
            ]
        )
        # Sheet が mount 時にグリッドへフォーカスしてタブを奪うので、
        # 全部が落ち着いてから最初のタブ(フォーム)へ戻す。
        self.call_after_refresh(self._start_on_form)

    def _start_on_form(self) -> None:
        self.query_one(TabbedContent).active = "tab-form"
        self.query_one(Form).fields[0].focus_input()

    def on_form_submitted(self, event: Form.Submitted) -> None:
        name = event.values["name"]
        plan = event.values["plan"]
        self.query_one("#form-result", Static).update(f"{name} さんを{plan}プランで登録しました")


if __name__ == "__main__":
    DemoApp().run()
