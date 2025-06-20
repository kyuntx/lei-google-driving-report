# Lei03/Lei03+/Lei04 運転日報ジェネレータ

Google CalendarとGoogle Maps APIを連携して、Yupiteru レーダー探知機 霧島レイモデル（Lei03/Lei03+/Lei04）向けの運転日報を自動生成します。

## 概要

このアプリケーションは、Google CalendarのGoogle Calendar連携機能によって記録された運転ログから、詳細な運転日報を生成します。運転ログは表形式で表示され、Excel互換のCSVファイルとしてダウンロードできます。

## 主な機能

- **Google OAuth2認証**: Google Calendar APIへの安全なアクセス
- **運転ログ自動抽出**: カレンダーイベントから運転データを自動抽出
- **住所変換**: GPS座標を住所に変換（Google Maps Reverse Geocoding API使用）
- **🆕 インテリジェントキャッシュ**: 同一座標のリバースジオコーディング結果をキャッシュしてAPI使用量を削減
- **🆕 キャッシュ管理インターフェイス**: キャッシュされたデータの表示・編集・削除機能
- **運転日報表示**: ブラウザ上で見やすい表形式で表示
- **CSV エクスポート**: Excel互換のShift_JIS形式でCSVダウンロード

## システム要件

- Python 3.7以上
- Google Cloud Platform アカウント
- Google Calendar API認証情報
- Google Maps API キー

## 必要なライブラリ

```
Flask
google-auth
google-auth-oauthlib
google-api-python-client
googlemaps
python-dateutil
python-dotenv
```

## セットアップ

### 1. Google Cloud Platformの設定

1. [Google Cloud Console](https://console.cloud.google.com/)にログイン
2. 新しいプロジェクトを作成（または既存プロジェクトを選択）
3. Google Calendar APIとGoogle Maps APIを有効化
4. OAuth2認証情報を作成し、`credentials.json`としてダウンロード
5. Google Maps API キーを作成

### 2. 通常のセットアップ（Python直接実行）

1. リポジトリをクローン
2. `credentials.json`をプロジェクトルートに配置
3. 必要なライブラリをインストール：
   ```bash
   pip install -r requirements.txt
   ```
4. 環境設定（オプション）：
   ```bash
   cp .env.example .env
   # .envファイルを編集してSECRET_KEYなどを設定
   ```
5. 実行：
   ```bash
   python app.py
   ```

### 3. Dockerを使用したセットアップ（推奨）

#### 前提条件
- Docker
- Docker Compose

#### 手順

1. リポジトリをクローン：
   ```bash
   git clone https://github.com/kyuntx/lei-google-driving-report.git
   cd lei-google-driving-report
   ```

2. `credentials.json`をプロジェクトルートに配置

3. 環境設定：
   ```bash
   cp .env.example .env
   # .envファイルを編集してSECRET_KEYなどを設定
   ```

4. Dockerコンテナでアプリケーションを起動：
   ```bash
   # バックグラウンドで起動
   docker-compose up -d
   
   # ログを確認
   docker-compose logs -f
   ```

5. アプリケーションにアクセス：
   ```
   http://localhost:5000
   ```

#### Docker関連のコマンド

```bash
# アプリケーションを停止
docker-compose down

# イメージを再ビルド
docker-compose build

# コンテナの状態確認
docker-compose ps

# ログ確認
docker-compose logs lei-driving-report

# キャッシュボリュームの確認
docker volume ls

# キャッシュボリュームの削除（キャッシュをリセットする場合）
docker volume rm lei-google-driving-report_geocoding_cache
```

アプリケーションは `http://localhost:5000` で起動します。

## 使用方法

### 1. 初期設定
1. アプリケーションにアクセス
2. 「Google認証」ボタンでGoogle アカウントにログイン
3. Google Calendar API のアクセス許可を承認

### 2. 日報生成
1. レポート生成フォームに以下を入力：
   - **開始日**・**終了日**: 集計期間（デフォルト：当月）
   - **カレンダーID**: 使用するカレンダー（デフォルト：プライマリカレンダー）
   - **Google Maps APIキー**: 住所変換用のAPIキー
2. 「レポート生成」をクリック

### 3. 結果確認・エクスポート
- ブラウザ上で運転日報を確認
- 「CSVダウンロード」でExcel形式のファイルをダウンロード

## 運転ログの記録形式

Google Calendarのイベントタイトルは以下の形式で記録してください：

```
距離{数値}km ({数値}km/l)
```

**例**: `距離15.2km (12.5km/l)`

- GPS座標はイベントの「場所」フィールドに記録されます
- 前回の運転終了地点が次回の出発地点として自動設定されます

## CSV出力形式

生成されるCSVファイルには以下の項目が含まれます：

| 項目 | 説明 |
|------|------|
| 出発時刻 | 運転開始時刻 |
| 到着時刻 | 運転終了時刻 |
| 所要時間(分) | 運転時間（分単位） |
| 出発地 | 出発地の住所 |
| 到着地 | 到着地の住所 |
| 移動距離 | 走行距離（km） |
| 燃費 | 燃費（km/l） |

## プロジェクト構造

```
lei-google-driving-report/
├── app.py                 # メインアプリケーション
├── templates/
│   ├── index.html        # メインページ
│   ├── report.html       # レポート表示ページ
│   └── cache.html        # キャッシュ管理ページ
├── requirements.txt      # Python依存関係
├── Dockerfile           # Dockerイメージ定義
├── docker-compose.yml   # Docker Compose設定
├── .dockerignore        # Docker除外ファイル
├── .gitignore           # Git除外ファイル
├── .env.example         # 環境変数テンプレート
├── credentials.json     # Google API認証情報（要設定）
├── CLAUDE.md           # 開発者向けドキュメント
└── README.md           # このファイル
```

## 🆕 キャッシュ機能について

### リバースジオコーディングキャッシュ

アプリケーションは、Google Maps APIの使用料削減のため、リバースジオコーディング結果を自動的にキャッシュします。

**特徴：**
- **永続キャッシュ**: SQLiteデータベース（`geocoding_cache.db`）を使用した永続的なキャッシュ
- **座標の丸め**: 小数点以下4桁の精度（約11m）で座標を丸めてキャッシュ効率を向上
- **自動管理**: 同一座標範囲での重複API呼び出しを自動的に回避
- **コスト削減**: 頻繁に訪問する場所のAPI使用量を大幅に削減

**動作：**
1. 初回アクセス時：Google Maps APIを呼び出して住所を取得し、結果をキャッシュ
2. 2回目以降：キャッシュから高速で住所を取得、API呼び出しなし

**キャッシュファイル：**
- `geocoding_cache.db` - Gitリポジトリから除外済み
- 削除すると次回実行時に再構築されます
- Docker環境では名前付きボリューム `geocoding_cache` として永続化

### キャッシュ管理インターフェイス

アプリケーションには、キャッシュエントリを表示・編集・削除できるWebインターフェイスが含まれています。

**アクセス方法：**
- メインページまたはレポートページの「キャッシュ管理」ボタンをクリック
- URL: `http://localhost:5000/cache`

**機能：**
- **キャッシュ一覧表示**: すべてのキャッシュエントリをページネーション付きで表示
- **住所編集**: 間違った住所を直接編集・修正
- **エントリ削除**: 個別または全体のキャッシュエントリ削除
- **Google Maps連携**: 各座標をGoogle Mapsで確認可能
- **リアルタイム更新**: ページ再読み込み不要のAJAX操作

**使用場面：**
- 住所変換結果が不正確な場合の手動修正
- 古いキャッシュデータの削除
- キャッシュ状況の確認とメンテナンス

## 注意事項

- `credentials.json`ファイルは機密情報のため、リポジトリには含まれていません
- 本番環境では、`app.py`の`secret_key`を環境変数から取得するよう変更してください
- Google Maps APIの使用には料金が発生する場合がありますが、キャッシュ機能により削減されます
- CSVファイルはShift_JIS形式でエクスポートされ、日本語版Excelで正しく表示されます
- キャッシュデータベース（`geocoding_cache.db`）は自動的に作成・管理されます

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## サポート

- Yupiteru レーダー探知機 霧島レイモデル のGoogle Calendar連携機能については、製品のマニュアルを参照してください。
- 霧島レイモデル以外のYupiteru製レーダー探知機でも利用できる可能性がありますが、未検証です。
- Lei01,Lei02,Lei05,Lei06,Sakura01,LeiLite,H6-Lei01/Sakura01/Chacha01はGoogleカレンダー連携機能がないため非対応です。（実装求む！）