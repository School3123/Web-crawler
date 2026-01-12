import streamlit as st
import os
import time
import requests
import shutil
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# ==========================================
# 設定・定数
# ==========================================
DOWNLOAD_DIR = "downloaded_site"
ZIP_NAME = "site_backup"

# ブラウザになりすますヘッダー (Robots.txt無視・アクセスブロック回避用)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.google.com/"
}

# ==========================================
# 関数定義
# ==========================================

def reset_directory():
    """保存用ディレクトリをリセット（削除して再作成）する"""
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    os.makedirs(DOWNLOAD_DIR)
    for sub in ["css", "js", "images", "fonts"]:
        os.makedirs(os.path.join(DOWNLOAD_DIR, sub), exist_ok=True)

def save_file(url, folder, log_container):
    """ファイルをダウンロードして保存する"""
    try:
        parsed = urlparse(url)
        if not parsed.netloc or not parsed.scheme:
            return

        filename = os.path.basename(parsed.path)
        # 拡張子がない、またはファイル名が長すぎる場合の処理
        if not filename or "." not in filename or len(filename) > 50:
            filename = f"file_{int(time.time()*1000)}.txt"
        
        # クエリパラメータ削除
        filename = filename.split('?')[0]
        
        save_path = os.path.join(DOWNLOAD_DIR, folder, filename)

        if os.path.exists(save_path):
            return # 既に存在する場合はスキップ

        # ダウンロード実行
        response = requests.get(url, headers=HEADERS, timeout=5)
        response.raise_for_status()

        with open(save_path, 'wb') as f:
            f.write(response.content)
            
        # ログ表示
        log_container.text(f"✔ Downloaded: {filename}")
        time.sleep(0.1) # 負荷軽減

    except Exception:
        # エラーは無視して続行（ログには出さない）
        pass

def create_zip():
    """ダウンロードしたフォルダをZIPに圧縮する"""
    shutil.make_archive(ZIP_NAME, 'zip', DOWNLOAD_DIR)
    return f"{ZIP_NAME}.zip"

# ==========================================
# UI (Streamlit) メイン処理
# ==========================================

st.set_page_config(page_title="Web Crawler", layout="centered")

st.title("🕷️ Web Site Downloader")
st.markdown("指定したURLの構成ファイル（HTML, CSS, JS, 画像）を一括ダウンロードします。")

# URL入力フォーム
target_url = st.text_input("Target URL", placeholder="https://example.com")

# 実行ボタン
if st.button("🚀 Start Crawling"):
    if not target_url:
        st.error("Please enter a URL.")
    else:
        # 処理開始
        reset_directory()
        status_text = st.empty()
        log_box = st.empty()
        
        try:
            with st.spinner('Accessing main page...'):
                # メインHTMLの取得
                res = requests.get(target_url, headers=HEADERS, timeout=10)
                res.raise_for_status()
                
                # HTML保存
                with open(os.path.join(DOWNLOAD_DIR, "index.html"), "w", encoding=res.encoding or "utf-8") as f:
                    f.write(res.text)
                
                soup = BeautifulSoup(res.text, "html.parser")
                
            status_text.success("Connection established! Downloading assets...")
            
            # ログ表示エリアの作成
            log_container = st.container()
            
            # プログレスバー（簡易）
            progress_bar = st.progress(0)
            
            # 取得対象のリストアップ
            links = soup.find_all("link", rel="stylesheet")
            scripts = soup.find_all("script")
            images = soup.find_all("img")
            
            total_assets = len(links) + len(scripts) + len(images)
            current_count = 0

            # 1. CSS
            for link in links:
                href = link.get("href")
                if href:
                    save_file(urljoin(target_url, href), "css", log_box)
                current_count += 1
                if total_assets > 0: progress_bar.progress(current_count / total_assets)

            # 2. JS
            for script in scripts:
                src = script.get("src")
                if src:
                    save_file(urljoin(target_url, src), "js", log_box)
                current_count += 1
                if total_assets > 0: progress_bar.progress(current_count / total_assets)

            # 3. Images
            for img in images:
                src = img.get("src")
                if src:
                    save_file(urljoin(target_url, src), "images", log_box)
                current_count += 1
                if total_assets > 0: progress_bar.progress(current_count / total_assets)

            progress_bar.progress(100)
            st.success("🎉 All tasks completed!")

            # ZIP圧縮
            zip_file = create_zip()
            
            # ダウンロードボタンの表示
            with open(zip_file, "rb") as fp:
                btn = st.download_button(
                    label="📥 Download ZIP File",
                    data=fp,
                    file_name="website_backup.zip",
                    mime="application/zip"
                )

        except Exception as e:
            st.error(f"Error: {e}")

st.markdown("---")
st.caption("⚠️ For educational and verification purposes only. Do not violate site terms of service.")
