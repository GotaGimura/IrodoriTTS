# AiMeru Voice Studio

藍 (ai) と 芽瑠 (meru) の掛け合いスクリプトを WAV 音声に変換する PySide6 デスクトップアプリケーションです。  
バックエンドに [Irodori-TTS-Server](https://github.com/Aratako/Irodori-TTS)（OpenAI 互換 TTS API）を使用します。

---

## 動作要件

| 項目 | 要件 |
|------|------|
| OS | macOS 12 以上 / Windows 10 以上 |
| Python | 3.11 以上 |
| Irodori-TTS-Server | 別途起動が必要（後述） |

---

## セットアップ手順

### 1. リポジトリをクローン

```bash
git clone <このリポジトリの URL>
cd IrodoriTTS
```

### 2. セットアップスクリプトを実行

**macOS / Linux:**

```bash
chmod +x setup.sh
./setup.sh
```

**Windows:**

`setup.bat` をダブルクリック、またはコマンドプロンプトで実行。

セットアップスクリプトは次のことを行います:
- Python 3.11 以上の確認
- `.venv/` 仮想環境の作成
- 依存ライブラリのインストール

### 3. 参照音声ファイルを配置

`voice_samples/` フォルダを作成し、参照音声 WAV ファイルを配置してください。  
**これらのファイルはリポジトリには含まれません（.gitignore で除外されています）。**

```
voice_samples/
  ai.wav    ← 藍の参照音声（10〜30 秒推奨、モノラル WAV）
  meru.wav  ← 芽瑠の参照音声（10〜30 秒推奨、モノラル WAV）
```

> ファイル名は任意です。アプリの「話者設定」タブでパスを指定できます。

### 4. Irodori-TTS-Server を起動

別のターミナルで Irodori-TTS-Server を起動します。  
サーバーのセットアップは [Irodori-TTS リポジトリ](https://github.com/Aratako/Irodori-TTS) を参照してください。

```bash
# Irodori-TTS のディレクトリで
uv run uvicorn irodori_openai_tts.app:app --host 127.0.0.1 --port 8088
```

### 5. AiMeru Voice Studio を起動

**macOS / Linux:**

```bash
./run.sh
```

**Windows:**

`run.bat` をダブルクリック、またはコマンドプロンプトで実行。

---

## 使い方

1. **プロジェクト設定タブ** で台本 Markdown ファイルと出力フォルダを指定
2. **話者設定タブ** で voice ID と参照音声ファイルを設定
3. **プロジェクト設定タブ** の「台本を読み込んでプレビューを更新」をクリック
4. **台本プレビュータブ** で内容を確認
5. **生成キュータブ** で生成を開始

### 台本フォーマット

```markdown
藍：こんにちは、藍です。
芽瑠：はじめまして、芽瑠です！

藍：今日はどうぞよろしく。
芽瑠：こちらこそ、よろしくお願いします。
```

---

## ファイル構成

```
IrodoriTTS/
├── aimeru/                 # アプリケーション本体
│   ├── gui/                # PySide6 GUI
│   ├── adapter.py          # Irodori-TTS-Server HTTP クライアント
│   ├── models.py           # データモデル
│   ├── parser.py           # Markdown パーサー
│   ├── mixer.py            # WAV ミキサー
│   ├── manifest.py         # プロジェクト状態の保存/読み込み
│   └── voice_checker.py    # 参照音声品質チェッカー
├── voice_samples/          # 参照音声置き場 (git 除外)
├── main.py                 # エントリーポイント
├── launch_gradio.py        # Gradio UI ランチャー
├── setup.sh                # セットアップ (macOS/Linux)
├── setup.bat               # セットアップ (Windows)
├── run.sh                  # 起動 (macOS/Linux)
├── run.bat                 # 起動 (Windows)
└── requirements.txt        # 依存ライブラリ
```

### 出力ファイル（git 除外）

```
<出力フォルダ>/
├── chunks/          # 台詞ごとの WAV ファイル
├── exports/
│   └── full_mix.wav # 全台詞を結合した最終 WAV
├── manifest.json    # 生成状態の記録
└── script_table.json
```

---

## Gradio UI ランチャー

Irodori-TTS の Gradio UI（声のデザインや TTS v3 直接操作）を起動できます。

```bash
python launch_gradio.py          # 両方起動
python launch_gradio.py --v3     # TTS v3 のみ
python launch_gradio.py --vd     # VoiceDesign のみ
python launch_gradio.py --no-browser  # ブラウザ自動起動なし
```

> **セキュリティ:** デフォルトは `127.0.0.1`（ローカルのみ）です。  
> LAN に公開する場合は `--network` フラグを追加してください（信頼できるネットワークのみ）。

---

## セキュリティについて

- **参照音声ファイル（WAV）は `.gitignore` で除外されています。**  
  音声データは個人のものです。誤ってリポジトリに含めないよう注意してください。
- **出力ファイル（chunks/, exports/, manifest.json）も除外されています。**  
  生成物に台詞テキストが含まれる場合は取り扱いに注意してください。
- **サーバー URL はデフォルト `http://localhost:8088`（ローカルのみ）です。**  
  外部サーバーを指定する場合は信頼できる接続（VPN など）を使用してください。
- **Gradio UI はデフォルトでローカルのみに公開されます。**  
  `--network` フラグによる外部公開は信頼できるネットワーク内でのみ行ってください。

---

## トラブルシューティング

### 「サーバーに接続できません」と表示される

Irodori-TTS-Server が起動しているか確認してください。  
プロジェクト設定タブの「接続確認」ボタンでテストできます。

### 音声が再生されない (macOS)

macOS では `afplay` コマンドを使用します。通常 OS 標準で含まれています。  
問題が続く場合はターミナルで `afplay --version` を確認してください。

### 音声が再生されない (Windows)

PySide6 の QMediaPlayer を使用しています。  
`PySide6-Addons` が正しくインストールされているか確認してください。

```bash
.venv\Scripts\pip install PySide6-Addons
```

### `ModuleNotFoundError: No module named 'aimeru'`

`main.py` があるディレクトリから実行してください。  
`run.sh` / `run.bat` を使うと正しいディレクトリから起動されます。
