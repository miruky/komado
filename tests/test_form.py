import re

from textual.app import App, ComposeResult
from textual.validation import Integer, Regex
from textual.widgets import Label

from komado import Form, FormField

EMAIL = Regex(
    re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    failure_description="メールアドレスの形式が不正です",
)


def passwords_match(values: dict[str, str]) -> str | None:
    if values["password"] != values["confirm"]:
        return "パスワードが一致していません"
    return None


class FormApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.submissions: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Form(
            FormField("名前", "name", required=True),
            FormField("メール", "email", validators=[EMAIL]),
            FormField(
                "年齢",
                "age",
                validators=[Integer(minimum=0, failure_description="0以上の整数で")],
            ),
            FormField("パスワード", "password", required=True, password=True),
            FormField("確認", "confirm", required=True, password=True),
            rules=[passwords_match],
        )

    def on_form_submitted(self, event: Form.Submitted) -> None:
        self.submissions.append(event.values)


def fill(form: Form, values: dict[str, str]) -> None:
    by_name = {field.field_name: field for field in form.fields}
    for name, value in values.items():
        by_name[name].value = value


VALID = {
    "name": "山田",
    "email": "yamada@example.com",
    "age": "30",
    "password": "himitsu",
    "confirm": "himitsu",
}


async def test_valid_submit_posts_message():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        fill(form, VALID)
        assert form.submit() is True
        await pilot.pause()
        assert app.submissions == [VALID]


async def test_required_field_blocks_submit():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        fill(form, {**VALID, "name": "  "})
        assert form.submit() is False
        await pilot.pause()
        assert app.submissions == []
        name_field = form.fields[0]
        assert name_field.error == "入力してください"


async def test_validator_failure_message_is_shown():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        fill(form, {**VALID, "email": "ヤマダ"})
        assert form.submit() is False
        await pilot.pause()
        assert form.fields[1].error == "メールアドレスの形式が不正です"


async def test_optional_empty_field_is_valid():
    app = FormApp()
    async with app.run_test():
        form = app.query_one(Form)
        fill(form, {**VALID, "email": "", "age": ""})
        assert form.submit() is True


async def test_cross_rule_failure_shows_form_error():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        fill(form, {**VALID, "confirm": "chigau"})
        assert form.submit() is False
        await pilot.pause()
        assert form.form_error == "パスワードが一致していません"
        assert app.submissions == []


async def test_form_error_clears_after_fix():
    app = FormApp()
    async with app.run_test():
        form = app.query_one(Form)
        fill(form, {**VALID, "confirm": "chigau"})
        form.submit()
        fill(form, VALID)
        assert form.submit() is True
        assert form.form_error == ""


async def test_live_validation_on_typing():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        form.fields[1].focus_input()
        await pilot.press("a")
        assert form.fields[1].error == "メールアドレスの形式が不正です"


async def test_submit_button_triggers_submit():
    app = FormApp()
    async with app.run_test(size=(80, 40)) as pilot:
        form = app.query_one(Form)
        fill(form, VALID)
        await pilot.click("#komado-form-submit")
        await pilot.pause()
        assert app.submissions == [VALID]


async def test_enter_in_input_triggers_submit():
    app = FormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        fill(form, VALID)
        form.fields[0].focus_input()
        await pilot.press("enter")
        await pilot.pause()
        assert app.submissions == [VALID]


async def test_values_property_collects_all_fields():
    app = FormApp()
    async with app.run_test():
        form = app.query_one(Form)
        fill(form, VALID)
        assert form.values == VALID


async def test_required_field_label_has_marker():
    app = FormApp()
    async with app.run_test():
        form = app.query_one(Form)
        required = form.fields[0]  # 名前(required=True)
        optional = form.fields[2]  # 年齢(required=False)
        required_label = required.query_one(".komado-field-label", Label)
        optional_label = optional.query_one(".komado-field-label", Label)
        assert "*" in str(required_label.render())
        assert "*" not in str(optional_label.render())


class BracketApp(App):
    def compose(self) -> ComposeResult:
        yield Form(FormField("重さ [kg]", "weight", required=True))


async def test_label_with_brackets_is_preserved():
    app = BracketApp()
    async with app.run_test():
        label = app.query_one(".komado-field-label", Label)
        assert "[kg]" in str(label.render())


class EmptyFormApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.submissions: list[dict[str, str]] = []

    def compose(self) -> ComposeResult:
        yield Form()

    def on_form_submitted(self, event: Form.Submitted) -> None:
        self.submissions.append(event.values)


async def test_empty_form_submits_with_no_values():
    app = EmptyFormApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        assert form.submit() is True
        await pilot.pause()
        assert app.submissions == [{}]
