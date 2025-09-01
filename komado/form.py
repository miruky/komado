"""バリデーション付きフォームウィジェット。

Textual標準の `Input` と `textual.validation` はフィールド単体の検証しか
持たない。ここではラベル・入力・エラー表示を束ねた各種フィールド
(`FormField` / `SelectField` / `SwitchField`)と、フィールド横断ルール・
送信制御を担う `Form` を提供する。

フィールドはすべて `Field` を継承し、必須チェック・検証・インラインエラー
表示・送信時フォーカスは基底側で共通化する。サブクラスは入力コントロールの
生成と値の読み書きだけを受け持つ。
"""

from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.markup import escape
from textual.message import Message
from textual.validation import Validator
from textual.widget import Widget
from textual.widgets import Button, Input, Label, Select, Static, Switch

from . import motion

CrossRule = Callable[[dict[str, str]], str | None]
"""フォーム全体を見るルール。値の辞書を受け取り、問題があればメッセージを返す。"""


class Field(Vertical):
    """フォーム1項目の基底。ラベル・コントロール・エラー表示を縦に束ねる。

    値はすべて文字列として扱う。サブクラスは入力コントロールを作る
    `_make_control` と、値を読み書きする `_read` / `_write` を実装する。
    必須チェック・検証・エラー表示・初期値リセットは基底が面倒を見る。
    """

    DEFAULT_CSS = """
    .komado-field {
        height: auto;
        margin-bottom: 1;
    }
    .komado-field > .komado-field-label {
        text-style: bold;
        color: $foreground 90%;
        padding: 0 1;
    }
    .komado-field.-invalid Input,
    .komado-field.-invalid Select {
        border: tall $error;
    }
    .komado-field > .komado-field-error {
        display: none;
        height: auto;
        color: $text-error;
        padding: 0 1;
    }
    .komado-field.-invalid > .komado-field-error {
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
        motion: bool = True,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self.add_class("komado-field")
        self.komado_motion = motion
        self.field_name = name
        self.label_text = label
        self.required = required
        self._validators = validators or []
        self._control = self._make_control()
        self._initial_value = self._read()
        self._error_text = ""
        self._error = Static("", classes="komado-field-error")

    def _make_control(self) -> Widget:
        raise NotImplementedError

    def _read(self) -> str:
        raise NotImplementedError

    def _write(self, value: str) -> None:
        raise NotImplementedError

    def compose(self) -> ComposeResult:
        # ラベルは利用側が決める任意の文字列なので、必須マーカーを足す前に
        # マークアップとして解釈されないようエスケープする([kg] などが消えない)。
        marker = " [$text-error]*[/]" if self.required else ""
        yield Label(f"{escape(self.label_text)}{marker}", classes="komado-field-label")
        yield self._control
        yield self._error

    @property
    def value(self) -> str:
        return self._read()

    @value.setter
    def value(self, new_value: str) -> None:
        self._write(new_value)

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

    def reset(self) -> None:
        """値を初期状態へ戻し、エラー表示を消す。"""
        self._write(self._initial_value)
        self._error_text = ""
        self._error.update("")
        self.set_class(False, "-invalid")

    def focus_input(self) -> None:
        self._control.focus()

    def _first_failure(self) -> str | None:
        text = self._read()
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


class FormField(Field):
    """1行テキスト入力の項目。

    検証は Textual の `Validator` をそのまま受け取り、値の変更と
    フォーカス喪失のたびに実行する。最初の失敗メッセージだけを
    入力欄の直下に表示する。
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
        self._placeholder = placeholder
        self._initial = initial
        self._password = password
        super().__init__(
            label, name, validators=validators, required=required, motion=motion, id=id
        )

    def _make_control(self) -> Input:
        return Input(
            value=self._initial,
            placeholder=self._placeholder,
            password=self._password,
            validators=self._validators,
        )

    def _read(self) -> str:
        return self._control.value

    def _write(self, value: str) -> None:
        self._control.value = value

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


class SelectField(Field):
    """選択肢から1つ選ぶ項目(ドロップダウン)。

    `options` は表示文字列のリスト、または (表示, 値) のタプルのリスト。
    値は選択肢の「値」を文字列として返し、未選択は空文字列になる。
    """

    def __init__(
        self,
        label: str,
        name: str,
        options: list[str] | list[tuple[str, str]],
        *,
        required: bool = False,
        prompt: str = "選択してください",
        value: str | None = None,
        motion: bool = True,
        id: str | None = None,
    ) -> None:
        self._options = [(o, o) if isinstance(o, str) else o for o in options]
        self._prompt = prompt
        self._initial = value
        super().__init__(label, name, required=required, motion=motion, id=id)

    def _make_control(self) -> Select:
        initial = self._initial if self._initial is not None else Select.NULL
        return Select(self._options, prompt=self._prompt, value=initial)

    def _read(self) -> str:
        value = self._control.value
        return "" if value is Select.NULL else str(value)

    def _write(self, value: str) -> None:
        self._control.value = value if value != "" else Select.NULL

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        self.validate_now()


class SwitchField(Field):
    """オン・オフを切り替える項目。値は ``"true"`` / ``"false"``。"""

    _TRUE = frozenset({"true", "1", "on", "yes"})

    def __init__(
        self,
        label: str,
        name: str,
        *,
        value: bool = False,
        motion: bool = True,
        id: str | None = None,
    ) -> None:
        self._initial = value
        super().__init__(label, name, motion=motion, id=id)

    def _make_control(self) -> Switch:
        return Switch(value=self._initial)

    def _read(self) -> str:
        return "true" if self._control.value else "false"

    def _write(self, value: str) -> None:
        self._control.value = value.strip().lower() in self._TRUE


class Form(Vertical):
    """各種フィールドと送信ボタンを持つフォーム。

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
    def fields(self) -> list[Field]:
        return list(self.query(Field))

    @property
    def values(self) -> dict[str, str]:
        return {field.field_name: field.value for field in self.fields}

    @property
    def form_error(self) -> str:
        """フィールド横断ルールのエラーメッセージ。空文字列なら問題なし。"""
        return self._form_error_text

    def submit(self) -> bool:
        """全検証を実行し、通れば Submitted を投げて True を返す。"""
        first_invalid: Field | None = None
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

    def reset(self) -> None:
        """全フィールドを初期状態へ戻し、フォームエラーも消す。"""
        for field in self.fields:
            field.reset()
        self._set_form_error("")

    def set_values(self, values: dict[str, str]) -> None:
        """名前を指定して値をまとめて入れる。未知の名前は読み飛ばす。"""
        by_name = {field.field_name: field for field in self.fields}
        for name, value in values.items():
            field = by_name.get(name)
            if field is not None:
                field.value = value

    def _set_form_error(self, message: str) -> None:
        self._form_error_text = message
        self._form_error.update(message)
        self.set_class(bool(message), "-has-error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button is self._submit:
            event.stop()
            self.submit()
