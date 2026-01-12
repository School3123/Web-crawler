import streamlit as st
import streamlit.components.v1 as components
import requests
from bs4 import BeautifulSoup
import os
import zipfile
import re
from urllib.parse import urljoin, urlparse
from pathlib import Path
import shutil

# ページ設定
st.set_page_config(page_title="Ultimate Web Crawler", layout="wide")

st.title("🕸️ 全資産取得型 Webクローラー")
st.caption("HTML/CSS/JS/画像に加え、CSS内のフォントや背景画像も階層構造で保存します。")

# --- 定数・設定 ---
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
}

# --- 関数定義 ---

def get_save_path(url, base_folder):
    """URLからローカルの保存先パスを生成する"""
    parsed = urlparse(url)
    path = parsed.path
    if not path or path.endswith('/'):
        path += "index.html"
    
    # ドメインごとの階層を維持したい場合は parsed.netloc を含める
    # 今回は対象サイト内を想定し、pathのみを利用
    full_path = Path(base_folder) / path.lstrip('/')
    return full_path

def download_asset(url, base_folder):
    """ファイルをダウンロードして保存。成功すればパスを返す。"""
    try:
        save_path = get_save_path(url, base_folder)
        if save_path.exists(): # 重複ダウンロード防止
            return save_path

        response = requests.get(url, headers=HEADERS, timeout=10, verify=False, stream=True)
        if response.status_code == 200:
            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return save_path
    except Exception:
        pass
    return None

def extract_assets_from_css(css_url, css_content):
    """CSS内の url() 関数からフォントや画像のURLを抽出する"""
    urls = set()
    # url(...) の中身を抽出する正規表現
    pattern = r'url\([\'"]?(.*?)[\'"]?\)'
    matches = re.findall(pattern, css_content)
    for match in matches:
        if not match.startswith(('data:', 'http:', 'https:')):
            # 相対パスを絶対パスに変換
            full_url = urljoin(css_url, match)
            urls.add(full_url)
        elif match.startswith(('http:', 'https:')):
            urls.add(match)
    return urls

def start_crawl(target_url):
    domain = urlparse(target_url).netloc
    base_dir = f"site_data_{domain.replace('.', '_')}"
    
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.makedirs(base_dir)

    all_assets = set()
    
    # 1. HTMLの取得と解析
    try:
        res = requests.get(target_url, headers=HEADERS, verify=False, timeout=10)
        html_content = res.text
        soup = BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        st.error(f"サイトにアクセスできません: {e}")
        return None, None

    # 各種タグからURLを抽出
    tags_attrs = {
        'img': ['src', 'data-src', 'srcset'],
        'link': ['href'], # CSS, Favicon, Fonts
        'script': ['src'],
        'source': ['src', 'srcset'],
        'video': ['src'],
        'audio': ['src'],
        'object': ['data']
    }

    for tag, attrs in tags_attrs.items():
        for element in soup.find_all(tag):
            for attr in attrs:
                val = element.get(attr)
                if val:
                    # srcset の場合は最初のURLのみ、または分割して処理
                    if attr == 'srcset':
                        val = val.split(',')[0].split(' ')[0]
                    all_assets.add(urljoin(target_url, val))

    # 2. ダウンロード処理 (CSSは中身も解析)
    st.write("### 📥 ダウンロード中...")
    log_area = st.empty()
    progress_bar = st.progress(0)
    
    asset_list = list(all_assets)
    total = len(asset_list)
    
    for i, asset_url in enumerate(asset_list):
        path = download_asset(asset_url, base_dir)
        if path:
            log_area.text(f"取得中: {os.path.basename(asset_url)}")
            
            # CSSファイルなら中身を解析してフォント等を追加取得
            if str(path).endswith('.css'):
                try:
                    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                        css_text = f.read()
                    extra_assets = extract_assets_from_css(asset_url, css_text)
                    for ea in extra_assets:
                        download_asset(ea, base_dir)
                except:
                    pass
        progress_bar.progress((i + 1) / total)
    
    # index.htmlの保存
    with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_content)

    return base_dir, html_content

def make_zip(source_dir, output_filename):
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                zipf.write(os.path.join(root, file), 
                           os.path.relpath(os.path.join(root, file), source_dir))

def display_tree(directory, level=0):
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

input_url = st.text_input("クローリング対象URL:", "https://example.com")
col1, col2 = st.columns(2)
start_btn = col1.button("🚀 クローリング開始 (全資産取得)")

if start_btn:
    if not input_url.startswith("http"):
        st.error("有効なURLを入力してください。")
    else:
        result_dir, raw_html = start_crawl(input_url)
        
        if result_dir:
            st.success("全ての資産をダウンロードしました！")

            tab1, tab2 = st.tabs(["📂 ファイル構造とZIP", "🖥️ プレビュー"])

            with tab1:
                st.subheader("生成されたディレクトリ構造")
                st.code(display_tree(result_dir))
                
                zip_name = f"{result_dir}.zip"
                make_zip(result_dir, zip_name)
                with open(zip_name, "rb") as f:
                    st.download_button("📥 ZIPファイルをダウンロード", f, file_name=zip_name)

            with tab2:
                st.info("※プレビューは外部リソースを読み込んで表示しています。")
                preview_html = raw_html.replace('<head>', f'<head><base href="{input_url}">', 1)
                components.html(preview_html, height=700, scrolling=True)
