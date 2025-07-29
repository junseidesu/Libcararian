from flask import Flask, render_template, request, session, redirect, url_for, send_file, jsonify
import os
from io import BytesIO
import uuid
from pypdf import PdfReader, PdfWriter
from flask_session import Session
from booklet import change_to_booklet, convert_to_B5
import zipfile
from dotenv import load_dotenv
from google.cloud import storage
import datetime

# --- 環境設定 ---
load_dotenv()

# App Engine環境で実行されているかを環境変数で判定
# GAE環境では'GAE_ENV'が'standard'で始まるため、これを利用するのが確実
IS_GAE = os.getenv('GAE_ENV', '').startswith('standard')

# GAE環境では/tmp/、ローカル環境ではtmp/ を使うようにパスを切り替え
TMP_PATH = "/tmp" if IS_GAE else "tmp"

app = Flask(__name__)

# --- Flaskおよびセッションの設定 ---
app.secret_key="20041007"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(TMP_PATH, "flask_session")

# --- ストレージ設定 ---
if IS_GAE:
    # GAE環境の場合：GCSクライアントを初期化
    storage_client = storage.Client()
    CLOUD_STORAGE_BUCKET = os.getenv("CLOUD_STORAGE_BUCKET")
    bucket = storage_client.bucket(CLOUD_STORAGE_BUCKET)
else:
    # ローカル環境の場合：ローカルフォルダを設定
    app.config["UPLOAD_FOLDER"] = os.path.join(TMP_PATH, "uploads")
    app.config["EDITED_FOLDER"] = os.path.join(TMP_PATH, "edited")
    # 必要なローカルフォルダを起動時に作成
    for folder in [app.config["UPLOAD_FOLDER"], app.config["EDITED_FOLDER"], app.config["SESSION_FILE_DIR"]]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

Session(app)

# --- ヘルパー関数 (コードの冗長性を減らすため) ---

def get_file_bytes(file_info):
    """ファイル情報を元に、GCSまたはローカルからファイルのバイトデータを取得する"""
    if IS_GAE:
        try:
            blob = bucket.blob(file_info["storedfile_name"])
            return blob.download_as_bytes()
        except Exception as e:
            print(f"GCS file retrieval error: {e}")
            return None
    else:
        try:
            with open(file_info["storedfile_path"], 'rb') as f:
                return f.read()
        except FileNotFoundError:
            print(f"File not found: {file_info['storedfile_path']}")
            return None

def delete_file(file_info):
    """ファイル情報を元に、GCSまたはローカルからファイルを削除する"""
    if IS_GAE:
        try:
            bucket.delete_blob(file_info["storedfile_name"])
        except Exception as e:
            print(f"GCS file deletion error: {e}")
    else:
        if os.path.exists(file_info["storedfile_path"]):
            os.remove(file_info["storedfile_path"])

# --- Flask ルート ---

@app.route("/")
def index():
    if "files_info" not in session:
        session["files_info"] = []
    file_names = [item["file_name"] for item in session["files_info"]]
    return render_template("index.html", file_names=file_names, is_gae=IS_GAE)

@app.route("/upload", methods=["POST"])
def upload_file():
    files = request.files.getlist("file")
    if "files_info" not in session:
        session["files_info"] = []
    
    files_info = session["files_info"]

    for file in files:
        if not file:
            continue
        
        storedfile_name = str(uuid.uuid4()) + "_" + file.filename
        file_data = {"file_id": uuid.uuid4(), "file_name": file.filename, "storedfile_name": storedfile_name}

        if IS_GAE:
            # GCSにアップロード
            blob = bucket.blob(storedfile_name)
            blob.upload_from_file(file, content_type=file.content_type)
        else:
            # ローカルに保存
            storedfile_path = os.path.join(app.config["UPLOAD_FOLDER"], storedfile_name)
            file.save(storedfile_path)
            file_data["storedfile_path"] = storedfile_path
        
        files_info.append(file_data)
        
    session["files_info"] = files_info
    print(files_info)
    return redirect(url_for("index"))

@app.route("/generate_signed_url", methods=["POST"])
def generate_signed_url():
    if not IS_GAE:
        return "GAE環境でのみ実行可能", 400
    else:
        file=request.files.get("file")
        if not file:
            return "ファイルが選択されていません", 400
        storedfile_name = str(uuid.uuid4()) + "_" + file.filename
        blob = bucket.blob(storedfile_name)
        signed_url = blob.generate_signed_url_v4(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=file.content_type,
        )
        return signed_url

@app.route("/clear")
def clear():
    if "files_info" in session:
        for item in session["files_info"]:
            delete_file(item)
        session["files_info"] = []
    return redirect(url_for("index"))

@app.route("/combine")
def combine():
    if "files_info" not in session or not session["files_info"]:
        return "No files to combine.", 400

    # booklet.pyがファイルパスではなくメモリオブジェクトを扱えるように
    # 各ファイルのバイトデータをリストとして渡す
    input_files_streams = [BytesIO(get_file_bytes(item)) for item in session["files_info"]]
    
    # 出力ファイルは一時的にローカル（GAEなら/tmp）に保存
    output_path = os.path.join(TMP_PATH, "combine.pdf")

    unnumbering_page_str = request.args.get("no-number-pages")
    start_page_str = request.args.get("start-number")

    unnumbering_page = int(unnumbering_page_str) if unnumbering_page_str else 0
    start_page = int(start_page_str) if start_page_str else 1

    change_to_booklet(
        input_files=input_files_streams,
        output_path=output_path,
        center_gap_mm=20,
        isNumbering=True if request.args.get("isNumbering") == "numbering" else False,
        isBooklet=True if request.args.get("isBooklet") == "booklet" else False,
        unnumbering_page=unnumbering_page,
        start_page=start_page
    )
    
    return send_file(
        output_path,
        as_attachment=True,
        mimetype="application/pdf",
        download_name="結合ファイル.pdf"
    )

@app.route("/preview/<filename>")
def preview(filename):
    if "files_info" not in session:
        return "File not found", 404
    
    target_file = next((item for item in session["files_info"] if item["file_name"] == filename), None)
    
    if not target_file:
        return "File not found", 404

    file_bytes = get_file_bytes(target_file)
    return send_file(
        BytesIO(file_bytes),
        mimetype="application/pdf",
        as_attachment=False
    )

@app.route("/combine_by_song", methods=["POST"])
def combine_by_song():
    data = request.get_json()
    if not data:
        return "Invalid JSON data", 400

    # 最初に全PDFを結合して、メモリ上に一つのPDFオブジェクトとして保持
    combined_pdf = PdfWriter()
    for file_info in session.get("files_info", []):
        pdf_bytes = get_file_bytes(file_info)
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            combined_pdf.add_page(page)
    
    # 曲ごとに分割・加工処理
    filename_list = []
    names_and_ranges_info = data.get("songs", [])
    initial_number = int(data.get("initial_number", 1))

    prefix_pairing = {"mixed": "混声", "female": "女声", "male": "男声"}
    converted_prefix = prefix_pairing.get(data.get("prefix"), "")

    for info in names_and_ranges_info:
        # ... (既存のロジックはほぼ同じ)
        number = info["number"]
        name = info["name"]
        start_page = int(info["start"]) - initial_number
        end_page = int(info["end"]) - initial_number

        tmp_writer = PdfWriter()
        for i in range(start_page, end_page + 1):
            if 0 <= i < len(combined_pdf.pages):
                page = combined_pdf.pages[i]
                page = convert_to_B5(page) # この関数はページオブジェクトを直接操作
                tmp_writer.add_page(page)
        
        # 加工したPDFを一時フォルダに保存
        filename = f"{converted_prefix}{number:02d}{name}.pdf"
        output_path = os.path.join(TMP_PATH, filename)
        filename_list.append(filename)
        with open(output_path, "wb") as f:
            tmp_writer.write(f)

    # ZIPファイルを作成してダウンロード
    zip_filename = f"{converted_prefix}song_pdfs.zip"
    zip_output_path = os.path.join(TMP_PATH, zip_filename)

    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in filename_list:
            path = os.path.join(TMP_PATH, filename)
            zf.write(path, arcname=filename)
            os.remove(path) # ZIPに追加後、一時ファイルを削除

    session["ZIP_FILENAME"] = zip_filename
    session["ZIP_OUTPUT_PATH"] = zip_output_path
    return redirect(url_for("zip_download"))


# 他のルート（/zip_download, /update_file_order, /delete）は、
# ファイルパスに依存していないため、基本的には修正不要です。
# ただし、/deleteはファイルの実体を削除する必要があるため修正します。

@app.route("/delete")
def delete():
    if "files_info" not in session:
        return redirect(url_for("index"))
    
    files_info = session["files_info"]
    
    # 削除対象をファイル名で特定（この部分は元のロジックを維持）
    # 注：同じファイル名が複数あった場合、すべて削除される
    files_to_keep = []
    for item in files_info:
        if item["file_name"] == "バビロン.pdf":
            delete_file(item) # GCS/ローカルからファイルを削除
        else:
            files_to_keep.append(item)
            
    session["files_info"] = files_to_keep
    return redirect(url_for("index"))


@app.route("/zip_download")
def zip_download():
    zip_filename = session.get("ZIP_FILENAME")
    zip_output_path = session.get("ZIP_OUTPUT_PATH")
    if not zip_filename or not zip_output_path:
        return "No ZIP file to download.", 404
        
    return send_file(
        zip_output_path,
        mimetype='application/zip', 
        as_attachment=True,
        download_name=zip_filename
    )

@app.route("/update_file_order", methods=["POST"])
def update_file_order():
    files_info = session.get("files_info", [])
    order = request.json.get("order", [])
    
    map_by_name = {item["file_name"]: item for item in files_info}
    
    # 順番データに存在するファイルのみで新しいリストを作成
    files_info_new = [map_by_name[name] for name in order if name in map_by_name]
    
    session["files_info"] = files_info_new
    # このルートは画面遷移を伴わないので、redirectではなく成功応答を返す
    return {"status": "success"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)