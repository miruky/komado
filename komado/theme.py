"""komado向けに整えたTextualテーマ。

Textual既定の彩度の高い配色を避け、温度のある中立色に苔色のアクセント1色で
そろえた昼(washi)・夜(sumizome)の2テーマを用意する。フォームやシートのように
情報量の多い画面でも、原色がうるさく主張せず文字が読みやすいことを狙う。

利用側は :func:`register_themes` でアプリへ登録し、``app.theme = "komado-sumizome"``
のように選ぶ。配色は意味トークン($primary など)経由なので、各ウィジェットの
スタイルを書き換えずに見た目だけ差し替えられる。
"""

from __future__ import annotations

from textual.theme import Theme

# 昼: 和紙のような温かい地色に、沈んだ苔色のアクセント。
WASHI = Theme(
    name="komado-washi",
    primary="#3f6b4f",
    secondary="#6b6557",
    accent="#3f6b4f",
    foreground="#26231c",
    background="#f4f1ea",
    surface="#faf7f1",
    panel="#ece8df",
    success="#3f6b4f",
    warning="#8a5a23",
    error="#9a4434",
    dark=False,
)

# 夜: 墨染めの沈んだ地色に、明度を上げた苔色。暗所でも文字が浮く。
SUMIZOME = Theme(
    name="komado-sumizome",
    primary="#86b896",
    secondary="#9b9486",
    accent="#86b896",
    foreground="#ece6da",
    background="#16140f",
    surface="#1f1c16",
    panel="#221f18",
    success="#86b896",
    warning="#d4a463",
    error="#d2887d",
    dark=True,
)

THEMES: list[Theme] = [WASHI, SUMIZOME]
"""komadoが提供するテーマの一覧(昼・夜)。"""

DEFAULT_THEME = SUMIZOME.name
"""端末は暗い背景が多いため、既定は夜テーマにする。"""


def register_themes(app: object) -> None:
    """アプリにkomadoのテーマを登録する。

    ``app`` は ``register_theme`` を持つ Textual の ``App``。登録後は
    コマンドパレットやコードからテーマ名で切り替えられる。
    """
    register = app.register_theme  # type: ignore[attr-defined]
    for theme in THEMES:
        register(theme)
