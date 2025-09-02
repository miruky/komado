<img src="docs/logo.svg" width="88" align="right" alt="komadoのロゴ">

# komado

[![CI](https://github.com/miruky/komado/actions/workflows/ci.yml/badge.svg)](https://github.com/miruky/komado/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![Textual](https://img.shields.io/badge/Textual-%E2%89%A50.80-0B0B0B)
![License](https://img.shields.io/badge/License-MIT-green)

**Textual向けのTUI部品集。検証つきフォームと数式が使える表計算グリッドを、アプリに数行で組み込める。**

## 概要

[Textual](https://textual.textualize.io/) には入力欄単体の検証(`textual.validation`)はあるが、その上の「フォーム」という単位は自分で組むしかない。ラベルとエラー表示を並べ、送信時に全項目を検証し、パスワード確認のような項目をまたぐルールを判定する——どのアプリでも同じものを毎回書くことになる。表についても同様で、`DataTable` は表示専用に近く、セルを編集して集計するスプレッドシート的な使い方には手が届かない。

komadoはこの2つの隙間を埋める。`Form` はFormField群の一括検証・フィールド横断ルール・送信メッセージまでを面倒見る。`Sheet` は数式バーで編集できるグリッドで、`=SUM(A1:A5)` のような数式を依存解決・循環検出つきで評価する。どちらも素のTextualウィジェットとして `compose()` に置くだけで動く。

社内ツールや運用CLIをTextualで書くたびに、設定入力フォームと小さな集計表を作り直していたのが出発点。アプリ本体より部品の作り直しに時間が掛かるのをやめたかった。

## アーキテクチャ

![アーキテクチャ図](docs/architecture.svg)

フォームの検証はTextual標準の `Validator` をそのまま受け取り、その外側に必須チェックとフィールド横断ルールを重ねる。表計算の数式評価はTextualに依存しない `Engine`(字句解析・再帰下降パーサ・メモ化評価器)に分離しており、ウィジェットを起動せずに単体テストできる。

## 技術スタック

| 領域 | 採用技術 |
|------|---------|
| 言語 | Python 3.12+ |
| TUIフレームワーク | Textual 0.80+ |
| 数式評価 | 自前実装(正規表現トークナイザ+再帰下降パーサ) |
| テスト | pytest + pytest-asyncio(Textual Pilot) |
| リンタ・フォーマッタ | Ruff |
| CI | GitHub Actions |

## 使い方

### フォーム

```python
from textual.app import App, ComposeResult
from textual.validation import Integer
from komado import Form, FormField, SelectField, SwitchField


def passwords_match(values: dict[str, str]) -> str | None:
    if values["password"] != values["confirm"]:
        return "パスワードが一致していません"
    return None


class SettingsApp(App):
    def compose(self) -> ComposeResult:
        yield Form(
            FormField("ユーザー名", "name", required=True),
            FormField("年齢", "age", validators=[Integer(minimum=0)]),
            SelectField("プラン", "plan", ["無料", "有料", "法人"], required=True),
            SwitchField("メール通知", "notify", value=True),
            FormField("パスワード", "password", required=True, password=True),
            FormField("パスワード(確認)", "confirm", required=True, password=True),
            rules=[passwords_match],
            submit_label="登録",
        )

    def on_form_submitted(self, event: Form.Submitted) -> None:
        # event.values == {"name": "...", "plan": "有料", "notify": "true", ...}
        self.exit(event.values)
```

検証は入力のたびに走り、失敗メッセージは入力欄の直下に出る。送信ボタンか入力欄でのEnterで `submit()` が呼ばれ、全項目とフィールド横断ルールを通過したときだけ `Form.Submitted` が飛ぶ。失敗時は最初の問題フィールドへフォーカスが移る。

フィールドは3種類ある。`FormField` は1行テキスト、`SelectField` は選択肢からの単一選択(未選択は空文字列)、`SwitchField` はオン・オフ(`"true"` / `"false"`)。どれも値は文字列で揃うので、`Form.values` は名前から値への素直な辞書になる。値をまとめて入れる `Form.set_values({...})` と、初期状態へ戻す `Form.reset()` も用意している。

### 表計算グリッド

```python
from textual.app import App, ComposeResult
from komado import Sheet


class BudgetApp(App):
    def compose(self) -> ComposeResult:
        yield Sheet(rows=12, cols=6)

    def on_mount(self) -> None:
        sheet = self.query_one(Sheet)
        sheet.load_rows([
            ["費目", "金額"],
            ["家賃", "82000"],
            ["食費", "41200"],
            ["合計", "=SUM(B2:B3)"],   # 表示は 123200 になる
        ])

    def on_sheet_cell_changed(self, event: Sheet.CellChanged) -> None:
        self.log(f"{event.ref} = {event.display}")
```

矢印キーでセルを移動し、Enterで数式バーにフォーカスして編集、もう一度Enterで確定する。DeleteまたはBackspaceでセルを消去する。対話編集はCtrl+Zで元に戻し、Ctrl+Yでやり直せる(履歴は変更したセルへカーソルを戻す)。CSVは `to_csv()` で書き出し、`load_csv(text)` で取り込む(取り込みは既存の内容を置き換える)。`clear()` で全セルを空にできる。

### 数式エンジン単体

`Engine` はTextualなしで使える。

```python
from komado import Engine

engine = Engine()
engine.set_cell("A1", "10")
engine.set_cell("A2", "32")
engine.set_cell("B1", "=SUM(A1:A2)")
engine.value("B1")    # 42.0
engine.display("B1")  # "42"
engine.set_cell("C1", "=C1")
engine.value("C1")    # "#CYCLE!"
engine.set_cell("D1", "=IF(B1 >= 40, 1, 0)")
engine.value("D1")    # 1.0  (比較とIF。偽の枝は評価しないので除算エラーを避けられる)
```

対応する数式は四則演算・括弧・単項マイナス・セル参照・範囲・比較(`= <> < > <= >=`、真は1・偽は0)。関数は集計の `SUM` `AVERAGE` `MIN` `MAX` `COUNT` `MEDIAN` `PRODUCT` `STDEV`、要素ごとの `ABS` `ROUND` `SQRT` `POWER` `MOD` `FLOOR` `CEIL` `INT` `SIGN`、論理の `AND` `OR` `NOT`(0以外を真として畳む)、そして条件分岐の `IF(条件, 真のとき, 偽のとき)`。`IF(AND(A1>=5, A1<=10), 1, 0)` のように組み合わせられる。エラーは `#DIV/0!` `#CYCLE!` `#VALUE!` `#NAME?` `#REF!` `#ERROR!` のコードでセルに表示される。文字列セルを参照する算術は `#VALUE!`、範囲集計では文字列と空セルは読み飛ばす。文字列を返す関数やセルの書式設定には対応していない。

### テーマ

Textual既定の彩度の高い配色を避けた、温度のある中立色＋苔色アクセント1色の昼・夜テーマを同梱する。意味トークン経由なのでウィジェットのスタイルには手を入れず差し替えられる。

```python
from komado import register_themes, DEFAULT_THEME

class MyApp(App):
    def on_mount(self) -> None:
        register_themes(self)
        self.theme = DEFAULT_THEME  # "komado-sumizome"(夜)。昼は "komado-washi"
```

登録後はコマンドパレット(Ctrl+P)からも切り替えられる。

### デモ

両ウィジェットを試せるデモアプリを同梱している。テーマも適用済み。

```
python -m komado.demo
```

## プロジェクト構成

- `komado/`
  - `form.py` — `Field`(基底)と `FormField` / `SelectField` / `SwitchField`、`Form`。検証・エラー表示・送信制御
  - `sheet.py` — `Sheet`。数式バー+DataTableのグリッド、undo/redoとCSV入出力
  - `formula.py` — `Engine`。数式の解析と評価(Textual非依存)
  - `motion.py` — アニメーションレベルを尊重するモーション補助
  - `theme.py` — 低彩度＋アクセント1色の昼・夜テーマ(`register_themes`)
  - `demo.py` — ショーケースアプリ
- `tests/` — 数式エンジンの単体テストとPilotによるウィジェット操作テスト
- `docs/` — ロゴとアーキテクチャ図

## はじめ方

前提: Python 3.12以上。

```
git clone https://github.com/miruky/komado.git
cd komado
python -m venv .venv && source .venv/bin/activate
make install   # pip install -e ".[dev]"
```

テストとlint:

```
make test   # pytest(Pilotでウィジェットを実際に操作する)
make lint   # ruff check + ruff format --check
```

## 設計方針

**Textualの流儀から外れない。** 部品はすべて素のWidgetで、メッセージ(`Form.Submitted` / `Sheet.CellChanged`)で結果を返す。独自のイベント機構や設定ファイルは持ち込まず、検証器もTextual標準の `Validator` をそのまま受け取る。

**数式エンジンはUIから切り離す。** `Engine` は文字列を受けて値を返すだけの純粋なPythonで、テストの大半はターミナルエミュレーションなしで走る。ウィジェット側は「編集のたびに全セルを再描画する」素朴な戦略で、依存グラフの差分更新はしない。グリッドは高々数百セルで、メモ化により再計算はセルあたり1回で済むからだ。

**書ける範囲を最初から区切る。** スプレッドシートの完全再現は狙わない。数式は集計と条件分岐に必要な語彙に絞り、対応しないこと(文字列を返す関数、セルの書式)はREADMEに明記する。

**動きは添えるが、止められるようにする。** 入場のフェードやセル確定の明滅といったモーションは、Textualのアニメーションレベル(`TEXTUAL_ANIMATIONS=none` で無効化、`prefers-reduced-motion` に相当)を尊重する。各ウィジェットに `motion=False` も渡せる。位置を動かすアニメーションは操作の妨げになるため使わない。

## ライセンス

[MIT](LICENSE)
