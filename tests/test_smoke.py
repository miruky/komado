import re

import komado


def test_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+", komado.__version__)


def test_public_api():
    for name in komado.__all__:
        assert hasattr(komado, name)


async def test_demo_app_boots():
    from komado.demo import DemoApp

    app = DemoApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.query_one(komado.Form)
        assert app.query_one(komado.Sheet)
