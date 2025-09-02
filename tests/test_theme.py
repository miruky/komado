import re

from textual.app import App

from komado.theme import DEFAULT_THEME, SUMIZOME, THEMES, WASHI, register_themes

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_two_themes_with_unique_names():
    names = [t.name for t in THEMES]
    assert names == ["komado-washi", "komado-sumizome"]
    assert len(set(names)) == len(names)


def test_themes_are_namespaced():
    for theme in THEMES:
        assert theme.name.startswith("komado-")


def test_light_and_dark_pair():
    assert WASHI.dark is False
    assert SUMIZOME.dark is True


def test_required_colors_are_valid_hex():
    for theme in THEMES:
        for color in (
            theme.primary,
            theme.accent,
            theme.foreground,
            theme.background,
            theme.success,
            theme.warning,
            theme.error,
        ):
            assert _HEX.match(color), f"{theme.name}: {color}"


def test_single_accent_matches_primary():
    # アクセントは1色だけ。primaryとaccentをそろえて主張を一点に絞る。
    for theme in THEMES:
        assert theme.accent == theme.primary


def test_default_is_dark():
    assert SUMIZOME.name == DEFAULT_THEME


async def test_register_makes_themes_selectable():
    app = App()
    async with app.run_test():
        register_themes(app)
        for theme in THEMES:
            assert theme.name in app.available_themes
        app.theme = DEFAULT_THEME
        assert app.theme == DEFAULT_THEME
