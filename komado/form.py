"""バリデーション付きフォームウィジェット。

Textual標準の `Input` と `textual.validation` はフィールド単体の検証しか
持たない。ここではラベル・入力欄・エラー表示を束ねた `FormField` と、
フィールド横断ルールと送信制御を担う `Form` を提供する。
"""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.validation import Validator
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Static

from . import motion

CrossRule = Callable[[dict[str, str]], str | None]
"""フォーム全体を見るルール。値の辞書を受け取り、問題があればメッセージを返す。"""


class FormField(Vertical):
    """ラベル・入力欄・インラインエラーを縦に束ねた1項目。

    検証は Textual の `Validator` をそのまま受け取り、値の変更と
    フォーカス喪失のたびに実行する。最初の失敗メッセージだけを
    入力欄の直下に表示する。
    """

    DEFAULT_CSS = """
    FormField {
        height: auto;
        margin-bottom: 1;
    }
    FormField > .komado-field-label {
        text-style: bold;
        color: $foreground 90%;
        padding: 0 1;
    }
    FormField.-invalid > Input {
        border: tall $error;
    }
    FormField > .komado-field-error {
        display: none;
        height: auto;
        color: $text-error;
        padding: 0 1;
    }
    FormField.-invalid > .komado-field-error {
        display: block;
    }
    """

    def __init__(
        self,
        label: str,
        name: str,
        *,
        validators: list[Validator] | None = None,
        required: bool = False,
        placeholder: str = "",
        initial: str = "",
        password: bool = False,
        motion: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.komado_motion = motion
        self.field_name = name
        self.label_text = label
        self.required = required
        self._validators = validators or []
        self._input = Input(
            value=initial,
            placeholder=placeholder,
            password=password,
            validators=self._validators,
        )
        self._error_text = ""
        self._error = Static("", classes="komado-field-error")

    def compose(self) -> ComposeResult:
        marker = " [$text-error]*[/]" if self.required else ""
        yield Label(f"{self.label_text}{marker}", classes="komado-field-label")
        yield self._input
        yield self._error

    @property
    def value(self) -> str:
        return self._input.value

    @value.setter
    def value(self, new_value: str) -> None:
        self._input.value = new_value

    @property
    def error(self) -> str:
        """現在表示中のエラーメッセージ。空文字列なら問題なし。"""
        return self._error_text

    def validate_now(self) -> str | None:
        """検証を実行し、最初の失敗メッセージを返して表示も更新する。"""
        message = self._first_failure()
        was_clear = self._error_text == ""
        self._error_text = message or ""
        self._error.update(self._error_text)
        self.set_class(message is not None, "-invalid")
        if message is not None and was_clear and motion.motion_allowed(self):
            motion.reveal(self._error)
        return message

    def focus_input(self) -> None:
        self._input.focus()

    def _first_failure(self) -> str | None:
        text = self._input.value
        if self.required and text.strip() == "":
            return "入力してください"
        if text == "":
            return None
        for validator in self._validators:
            result = validator.validate(text)
            if not result.is_valid:
                descriptions = result.failure_descriptions
                return descriptions[0] if descriptions else "入力が正しくありません"
        return None

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self.validate_now()

    def on_input_blurred(self, event: Input.Blurred) -> None:
        event.stop()
        self.validate_now()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enterで送信ボタンと同じ動きをするよう、親のFormに委ねる。"""
        event.stop()
        form = next(
            (node for node in self.ancestors_with_self if isinstance(node, Form)),
            None,
        )
        if form is not None:
            form.submit()


class Form(Vertical):
    """FormField群と送信ボタンを持つフォーム。

    送信時に全フィールドとフィールド横断ルールを検証し、
    すべて通れば `Form.Submitted` を投げる。失敗したら最初の
    問題フィールドへフォーカスを移す。
    """

    DEFAULT_CSS = """
    Form {
        height: auto;
        padding: 1 2;
    }
    Form > .komado-form-error {
        display: none;
        height: auto;
        color: $text-error;
        background: $error 12%;
        border-left: thick $error;
        padding: 0 1;
        margin-bottom: 1;
    }
    Form.-has-error > .komado-form-error {
        display: block;
    }
    Form > #komado-form-submit {
        margin-top: 1;
    }
    """

    class Submitted(Message):
        """検証をすべて通過した送信。values はフィールド名から値への辞書。"""

        def __init__(self, form: Form, values: dict[str, str]) -> None:
            super().__init__()
            self.form = form
            self.values = values

    def __init__(
        self,
        *children: Widget,
        rules: list[CrossRule] | None = None,
        submit_label: str = "送信",
        motion: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(*children)
        if id is not None:
            self.id = id
        self.komado_motion = motion
        self._rules = rules or []
        self._form_error_text = ""
        self._form_error = Static("", classes="komado-form-error")
        self._submit = Button(submit_label, variant="primary", id="komado-form-submit")

    def compose(self) -> ComposeResult:
        yield self._form_error
        yield self._submit

    def on_mount(self) -> None:
        motion.reveal_sequence(self.fields, gate=self)

    @property
    def fields(self) -> list[FormField]:
        return list(self.query(FormField))

    @property
    def values(self) -> dict[str, str]:
        return {field.field_name: field.value for field in self.fields}

    @property
    def form_error(self) -> str:
        """フィールド横断ルールのエラーメッセージ。空文字列なら問題なし。"""
        return self._form_error_text

    def submit(self) -> bool:
        """全検証を実行し、通れば Submitted を投げて True を返す。"""
        first_invalid: FormField | None = None
        for field in self.fields:
            if field.validate_now() is not None and first_invalid is None:
                first_invalid = field
        if first_invalid is not None:
            self._set_form_error("")
            first_invalid.focus_input()
            return False
        values = self.values
        for rule in self._rules:
            message = rule(values)
            if message is not None:
                self._set_form_error(message)
                return False
        self._set_form_error("")
        self.post_message(self.Submitted(self, values))
        return True

    def _set_form_error(self, message: str) -> None:
        self._form_error_text = message
        self._form_error.update(message)
        self.set_class(bool(message), "-has-error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button is self._submit:
            event.stop()
            self.submit()
