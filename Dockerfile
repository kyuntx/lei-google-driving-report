# Python 3.12スリムイメージを使用
FROM python:3.12-slim

# メンテナー情報
LABEL maintainer="kyun <kazuki@clovertown.jp>"
LABEL description="Lei Google Driving Report Generator"

# 作業ディレクトリを設定
WORKDIR /app

# システムパッケージの更新とタイムゾーン設定
RUN apt-get update && apt-get install -y \
    tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -fs /usr/share/zoneinfo/Asia/Tokyo /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata

# Python依存関係ファイルをコピー
COPY requirements.txt .

# Python依存関係をインストール
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# アプリケーションファイルをコピー
COPY app.py .
COPY templates/ templates/
COPY CLAUDE.md .

# キャッシュディレクトリを作成
RUN mkdir -p /app/cache

# 非rootユーザーを作成してセキュリティを向上
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# アプリケーションディレクトリの所有権を変更
RUN chown -R appuser:appgroup /app

# 非rootユーザーに切り替え
USER appuser

# ポート5000を公開
EXPOSE 5000

# ヘルスチェックを追加
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# アプリケーションを起動
CMD ["python", "app.py"]