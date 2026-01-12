import streamlit as st
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup
import os
import zipfile
from urllib.parse import urljoin, urlparse
from pathlib import Path
import shutil

# ページ設定
st.set_page_config(page_title="Web Asset Downloader & Previewer", layout="wide")

st.title("🌐 Webサイト資産クローラー & プレビュー")
st.caption("指定したURLのファイルをダウンロードし、階層構造の確認とプレビュー表示を行います。")

# --- 関数定義 ---

def download_file(url, folder):
    """ファイルをダウンロードして保存する"""
    try:
        # User-Agentを設定してブロックを回避しやすくする
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, stream=True, timeout=10, verify=False, headers=headers)
        if response.status_code == 200:
            parsed_url = urlparse(url)
            relative_path = parsed_url.path.lstrip('/')
            if not relative_path or relative_path.endswith('/'):
                relative_path += "index.html"
            
            save_path = Path(folder) / relative_path
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return str(save_path)
    except Exception:
        return None
    return None

def get_all_assets(url):
    """HTMLから各種資産のURLを抽出する"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.get(url, timeout=10, headers=headers)
        soup = BeautifulSoup(response.text, 'html.parser')
        assets = set()

        tags_attrs = {
            'img': 'src',
            'link': 'href',
            'script': 'src',
            'source': 'src',
            'video': 'src',
            'a': 'href'
        }

        for tag, attr in tags_attrs.items():
            for element in soup.find_all(tag):
                asset_url = element.get(attr)
                if asset_url:
                    full_url = urljoin(url, asset_url)
                    assets.add(full_url)
        
        return assets, response.text
    except Exception as e:
        st.error(f"エラーが発生しました: {e}")
        return set(), ""

def make_zip(source_dir, output_filename):
    """ディレクトリをZIP化する"""
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(os.path.join(root, file), 
                           os.path.relpath(os.path.join(root, file), source_dir))

def display_tree(directory, level=0):
    """ディレクトリ階層を文字列で作成する"""
    items = sorted(os.listdir(directory))
    tree_str = ""
    for item in items:
        path = os.path.join(directory, item)
        if os.path.isdir(path):
            tree_str += "  " * level + "📁 " + item + "/\n"
            tree_str += display_tree(path, level + 1)
        else:
            tree_str += "  " * level + "📄 " + item + "\n"
    return tree_str

# --- UI部分 ---

target_url = st.text_input("クローリング対象URLを入力してください:", "https://example.com")
download_btn = st.button("クローリング開始")

if download_btn:
    if not target_url.startswith("http"):
        st.error("有効なURLを入力してください。")
    else:
        domain = urlparse(target_url).netloc
        base_dir = f"downloads_{domain.replace('.', '_')}"
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with st.spinner('ファイルをクローリング中...'):
            assets, html_content = get_all_assets(target_url)
            
            # HTMLを保存
            with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(html_content)

            # 各種ファイルのダウンロード
            progress_bar = st.progress(0)
            asset_list = list(assets)
            total = len(asset_list)
            
            for i, asset_url in enumerate(asset_list):
                download_file(asset_url, base_dir)
                progress_bar.progress((i + 1) / total)

        st.success(f"ダウンロード完了！")

        # タブに分けて表示
        tab1, tab2 = st.tabs(["📁 ファイル構成 & ダウンロード", "👁️ プレビュー"])

        with tab1:
            st.subheader("ファイル階層構造")
            st.code(display_tree(base_dir))

            # ZIP作成とダウンロードボタン
            zip_name = f"{base_dir}.zip"
            make_zip(base_dir, zip_name)
            with open(zip_name, "rb") as f:
                st.download_button(
                    label="📥 全ファイルをZIPでダウンロード",
                    data=f,
                    file_name=zip_name,
                    mime="application/zip"
                )

        with tab2:
            st.subheader("取得したHTMLのプレビュー")
            st.info("※プレビュー用に一時的にベースURLを補完して表示しています。")
            
            # プレビュー用にHTMLを加工（相対パスを絶対パスとして解釈させるため<base>タグを挿入）
            preview_html = html_content.replace(
                '<head>', f'<head><base href="{target_url}">', 1
            )
            
            # iframeでHTMLを表示
            components.html(preview_html, height=600, scrolling=True)
