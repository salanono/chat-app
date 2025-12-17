# Chat Support App（チャットサポートアプリ）

Web サイトに設置できる **チャットウィジェット** と  
**管理画面（オペレーター対応）** を備えた  
カスタマーサポート向けチャットアプリです。

Bot による一次対応と、必要に応じた **有人対応（ハンドオフ）** を切り替えることで、  
問い合わせ対応の効率化・運用負担の軽減を目的としています。

---

## 🔍 概要

- Web サイトに **iframe / script 1 行** で設置可能なチャットウィジェット
- Bot による選択肢ベースの自動応答
- オペレーターとのリアルタイムチャット（WebSocket）
- 管理画面からのセッション管理・メッセージ対応
- API キーによる **企業単位の分離設計**

---

## 🎯 想定ユースケース

- Web サイトのお問い合わせ対応
- よくある質問の自動応答
- オペレーター対応が必要な場合のみ有人接続
- 小規模〜中規模のカスタマーサポート運用

---

## ✨ 主な機能

### ウィジェット（訪問者側）

- チャットウィジェットの埋め込み表示
- Bot ウェルカムメッセージ表示
- 選択肢ベースの会話（入力欄なし）
- オペレーター接続のリクエスト
- 画像アップロード対応

### 管理画面（管理者 / オペレーター）

- セッション一覧・未読管理
- リアルタイムメッセージ表示（Socket.IO）
- オペレーターからの返信・画像送信
- セッションのクローズ管理
- Bot 設定（ウェルカムメッセージ・選択肢）
- API キーの発行・無効化

---

## 🏗 システム構成（簡易）

[ Webサイト ]
     |
     | iframe / script
     v
[ チャットウィジェット (Vue) ]
     |  HTTP / WebSocket
     v
[ Backend API (FastAPI) ]
     |
     v
[ PostgreSQL ]

---

## 🧰 使用技術

### フロントエンド

- Vue 3
- Vite
- JavaScript / HTML / CSS

### バックエンド

- Python
- FastAPI
- SQLAlchemy（Async）
- Socket.IO

### データベース

- PostgreSQL

### インフラ / 開発環境

- Docker / Docker Compose
- Nginx（フロント配信）
- JWT 認証

---

## 🔐 認証・セキュリティ

- 管理画面は **JWT 認証**
- ウィジェットは **API キー認証**
- API キーにより会社（Company）単位でデータを分離
- 無効化された API キーは利用不可

---

## 📁 ディレクトリ構成（抜粋）

.
├── backend/
│   ├── app/
│   │   ├── api/           # APIルート定義
│   │   ├── models.py     # DBモデル定義（Company / User / Session / Message など）
│   │   ├── auth.py       # 認証処理（JWT）
│   │   ├── db.py         # DB接続設定
│   │   └── main.py       # FastAPIエントリーポイント
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── pages/        # 管理画面・ウィジェット画面
│   │   ├── components/   # 共通コンポーネント
│   │   └── main.js
│   ├── public/
│   ├── Dockerfile
│   └── vite.config.js
│
├── docker-compose.yml
├── .gitignore
└── README.md

---

## 🚀 起動方法（ローカル）

### 1. リポジトリをクローン

```bash
git clone <repository-url>
cd chat-app
```

### 2. Docker 起動

docker compose up --build

### 3. 初期 DB セットアップ

docker compose exec backend python /app/scripts/init_db.py

### 4. 管理画面へアクセス

http://localhost:5173/admin/login

---

## 🧪 デモの流れ（想定）

1. 管理画面にログイン

2. Bot 設定・API キー発行

3. Web サイトにチャットウィジェット設置

4. Bot での自動応答

5. オペレーター接続

6. 管理画面でリアルタイム対応

---

## 🔧 技術的な工夫ポイント

- API キーによる マルチテナント設計

- Bot 内完結時は セッションを作成しない設計

- WebSocket を用いたリアルタイム通信

- DB 正規化とリレーション設計

---

## 🚧 今後の改善点

- 管理画面の検索・フィルタ機能強化

- ファイルストレージの外部化（S3 等）

- 権限管理の拡張

- 多言語対応

- ログ・監視機能の追加

---

## 📝 補足

本アプリは 学習・ポートフォリオ目的 で作成しています。
実運用を想定した設計・拡張性を意識しつつ、
シンプルで理解しやすい構成を重視しました。

---

## 👤 Author

- 名前：更家諒

- 用途：企業選考用ポートフォリオ
