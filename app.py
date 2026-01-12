import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import zipfile
from urllib.parse import urljoin, urlparse
from pathlib import Path
import shutil

# ページ設定
st.set_page_config(page_title="Web Asset Downloader", layout="wide")

st.title("🌐 Webサイト資産クローラー")
st.caption("指定したページで使用されている画像、JS、CSS、ファイルを階層構造で保存します。")

# --- 関数定義 ---

def download_file(url, folder):
    """ファイルをダウンロードして保存する"""
    try:
        response = requests.get(url, stream=True, timeout=10, verify=False) # robots.txt無視のため単純にリクエスト
        if response.status_code == 200:
            # URLからパスを解析
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
    except Exception as e:
        return None
    return None

def get_all_assets(url):
    """HTMLから各種資産のURLを抽出する"""
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        assets = set()

        # タグと属性の定義
        tags_attrs = {
            'img': 'src',
            'link': 'href',
            'script': 'src',
            'source': 'src',
            'video': 'src',
            'a': 'href' # ファイル(pdf, zip等)用
        }

        for tag, attr in tags_attrs.items():
            for element in soup.find_all(tag):
                asset_url = element.get(attr)
                if asset_url:
                    # 絶対パスに変換
                    full_url = urljoin(url, asset_url)
                    # 外部ドメインを除外したい場合はここでフィルタリング可能
                    # 今回は指定ドメイン内のリソースを優先的に取得
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
    """ディレクトリ階層を表示する"""
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
        st.error("有効なURL(http:// または https://)を入力してください。")
    else:
        # 保存先ディレクトリの準備
        domain = urlparse(target_url).netloc
        base_dir = f"downloads_{domain}"
        if os.path.exists(base_dir):
            shutil.rmtree(base_dir)
        os.makedirs(base_dir)

        with st.spinner('ファイルを解析・ダウンロード中...'):
            # HTML保存
            assets, html_content = get_all_assets(target_url)
            with open(os.path.join(base_dir, "index.html"), "w", encoding="utf-8") as f:
                f.write(html_content)

            # 資産のダウンロード
            progress_bar = st.progress(0)
            asset_list = list(assets)
            total = len(asset_list)
            
            downloaded_count = 0
            for i, asset_url in enumerate(asset_list):
                # 特定の拡張子や同一ドメインのものに限定するロジックを入れるとより綺麗になります
                download_file(asset_url, base_dir)
                progress_bar.progress((i + 1) / total)
                downloaded_count += 1

        st.success(f"完了！ {downloaded_count} 個のリソースを処理しました。")

        # 階層表示
        st.subheader("📁 生成されたファイル構成")
        st.code(display_tree(base_dir))

        # ZIP作成
        zip_name = f"{base_dir}.zip"
        make_zip(base_dir, zip_name)

        # ダウンロードボタン
        with open(zip_name, "rb") as f:
            st.download_button(
                label="📥 ZIPファイルをダウンロード",
                data=f,
                file_name=zip_name,
                mime="application/zip"
            )
