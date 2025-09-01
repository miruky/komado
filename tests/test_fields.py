from textual.app import App, ComposeResult

from komado import Form, FormField, SelectField, SwitchField


class FieldsApp(App):
    def compose(self) -> ComposeResult:
        yield Form(
            FormField("名前", "name", required=True, initial="初期"),
            SelectField("国", "country", ["日本", "米国"], required=True),
            SwitchField("通知", "notify", value=True),
        )


def by_name(form: Form, name: str):
    return next(field for field in form.fields if field.field_name == name)


async def test_select_starts_blank_and_enforces_required():
    app = FieldsApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        country = by_name(form, "country")
        assert country.value == ""
        assert country.validate_now() == "入力してください"
        country.value = "日本"
        await pilot.pause()
        assert country.value == "日本"
        assert country.validate_now() is None


async def test_switch_reads_true_false():
    app = FieldsApp()
    async with app.run_test():
        notify = by_name(app.query_one(Form), "notify")
        assert notify.value == "true"
        notify.value = "false"
        assert notify.value == "false"


async def test_form_values_cover_all_field_types():
    app = FieldsApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        form.set_values({"name": "山田", "country": "米国"})
        await pilot.pause()
        assert form.values == {"name": "山田", "country": "米国", "notify": "true"}


async def test_set_values_ignores_unknown_names():
    app = FieldsApp()
    async with app.run_test():
        form = app.query_one(Form)
        form.set_values({"name": "佐藤", "unknown": "x"})
        assert form.values["name"] == "佐藤"


async def test_reset_restores_initial_and_clears_error():
    app = FieldsApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        name = by_name(form, "name")
        name.value = "変更後"
        name.validate_now()
        form.set_values({"country": "日本"})
        await pilot.pause()
        form.reset()
        await pilot.pause()
        assert name.value == "初期"
        assert name.error == ""
        assert by_name(form, "country").value == ""


async def test_submit_blocks_until_required_select_chosen():
    app = FieldsApp()
    async with app.run_test() as pilot:
        form = app.query_one(Form)
        form.set_values({"name": "山田"})
        await pilot.pause()
        assert form.submit() is False
        form.set_values({"country": "日本"})
        await pilot.pause()
        assert form.submit() is True
