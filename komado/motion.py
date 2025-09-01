"""ウィジェットに意味のある動きを添えるための小さなヘルパー。

Textualのアニメーションは `App.animation_level` で制御され、環境変数
`TEXTUAL_ANIMATIONS=none` を渡すと完全に止まる。これがブラウザの
`prefers-reduced-motion: reduce` に相当する。ここではその判定を一点に
集約し、無効なときはアニメーションを一切使わず最終状態へ即座に移す。
ウィジェット個別に `motion=False` を指定しても止められる。

動きは「フェード(opacity)」と「色の明滅(tint)」に限る。位置を動かす
offsetアニメーションは、操作中の当たり判定を動かしてしまうため使わない。
"""

from __future__ import annotations

from collections.abc import Iterable

from textual.color import Color
from textual.widget import Widget

REVEAL_DURATION = 0.28
"""1要素がフェードインしきるまでの秒数。"""

REVEAL_STAGGER = 0.06
"""連続要素を入場させるときの、1要素あたりの遅延。"""

FLASH_DURATION = 0.5
"""明滅(変更通知)が消えるまでの秒数。"""


def motion_allowed(widget: Widget) -> bool:
    """このウィジェットでアニメーションを再生してよいか。

    `motion=False` 指定か、アプリのアニメーションレベルが ``none`` の
    どちらかなら再生しない。
    """
    if not getattr(widget, "komado_motion", True):
        return False
    try:
        app = widget.app
    except Exception:
        return False
    return app.animation_level != "none"


def reveal(widget: Widget, *, delay: float = 0.0) -> None:
    """フェードインさせる。再生しないときは不透明のまま即表示する。"""
    if not motion_allowed(widget):
        widget.styles.opacity = 1.0
        return
    widget.styles.opacity = 0.0
    widget.styles.animate("opacity", 1.0, duration=REVEAL_DURATION, delay=delay)


def reveal_sequence(
    widgets: Iterable[Widget], *, gate: Widget, step: float = REVEAL_STAGGER
) -> None:
    """複数要素を少しずつ遅らせて入場させる(スタッガ)。

    再生可否は ``gate``(ふつう親ウィジェット)で一括判定する。
    """
    items = list(widgets)
    if not motion_allowed(gate):
        for widget in items:
            widget.styles.opacity = 1.0
        return
    for index, widget in enumerate(items):
        reveal(widget, delay=index * step)


def flash(widget: Widget, color: Color) -> None:
    """一瞬だけ色を重ねてから引き、その要素が変化したことを知らせる。"""
    if not motion_allowed(widget):
        return
    widget.styles.tint = color.with_alpha(0.45)
    widget.styles.animate("tint", color.with_alpha(0.0), duration=FLASH_DURATION)
