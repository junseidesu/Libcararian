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

# =============================================================================
# 環境設定
# =============================================================================
load_dotenv()

# App Engine環境判定
# GAE環境では'GAE_ENV'環境変数が'standard'で始まる
IS_GAE = os.getenv('GAE_ENV', '').startswith('standard')

# 一時ファイル保存パス設定
# GAE環境: /tmp、ローカル環境: tmp
TMP_PATH = "/tmp" if IS_GAE else "tmp"

# =============================================================================
# Flaskアプリケーション設定
# =============================================================================
app = Flask(__name__)

# セッション設定
app.secret_key="20041007"
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(TMP_PATH, "flask_session")

# =============================================================================
# ストレージ設定
# =============================================================================
if IS_GAE:
    # GAE環境: Google Cloud Storage設定
    storage_client = storage.Client()
    CLOUD_STORAGE_BUCKET = os.getenv("CLOUD_STORAGE_BUCKET")
    bucket = storage_client.bucket(CLOUD_STORAGE_BUCKET)
else:
    # ローカル環境: ローカルディレクトリ設定
    app.config["UPLOAD_FOLDER"] = os.path.join(TMP_PATH, "uploads")
    app.config["EDITED_FOLDER"] = os.path.join(TMP_PATH, "edited")
    
    # 必要なディレクトリを作成
    for folder in [app.config["UPLOAD_FOLDER"], app.config["EDITED_FOLDER"], app.config["SESSION_FILE_DIR"]]:
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

Session(app)

# =============================================================================
# ヘルパー関数
# =============================================================================

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

# =============================================================================
# Flaskルート
# =============================================================================

@app.route("/")
def index():
    if "files_info" not in session:
        session["files_info"] = []
    file_names = [item["file_name"] for item in session["files_info"]]
    return render_template("index.html", file_names=file_names, is_gae=IS_GAE)

@app.route("/upload", methods=["POST"])
def upload_file():
    if IS_GAE:
        return "GAE環境ではこのルートは使えません"
    files = request.files.getlist("file")
    if "files_info" not in session:
        session["files_info"] = []
    
    files_info = session["files_info"]

    for file in files:
        if not file:
            continue
        
        storedfile_name = str(uuid.uuid4()) + "_" + file.filename
        file_data = {"file_id": uuid.uuid4(), "file_name": file.filename, "storedfile_name": storedfile_name}


        # ローカル環境: ローカルファイルに保存
        storedfile_path = os.path.join(app.config["UPLOAD_FOLDER"], storedfile_name)
        file.save(storedfile_path)
        file_data["storedfile_path"] = storedfile_path
        
        files_info.append(file_data)
        
    session["files_info"] = files_info
    print(files_info)
    return redirect(url_for("index"))

@app.route("/generate_signed_url", methods=["POST"])
def gen_signed_url():
    if not IS_GAE:
        return "GAE環境でのみ実行可能", 400
    else:
        data=request.get_json()
        file_name = data['file_name']
        file_type = data['file_type']
        if not file_name or not file_type:
            print("ノーファイル")
            return "ファイルが選択されていません", 400
        
        storedfile_name = str(uuid.uuid4()) + "_" + file_name
        file_data = {
            "file_id": str(uuid.uuid4()),
            "file_name": file_name,
            "storedfile_name": storedfile_name,
            "uploaded": False  # アップロード完了フラグ
        }
    
        if "files_info" not in session:
            session["files_info"] = []
        session["files_info"].append(file_data)
        print(storedfile_name)
            
        blob = bucket.blob(storedfile_name)
        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="PUT",
            content_type=file_type
        )

        return {
            "signed_url": signed_url,
            "file_id": file_data["file_id"]
        }
    
@app.route("/confirm_upload", methods=["POST"])
def confirm_upload():
    """クライアントからアップロード完了通知を受け取る"""
    data = request.get_json()
    file_id = data.get("file_id")
    
    # セッション内のファイル情報を更新
    files_info = session.get("files_info", [])
    for file_info in files_info:
        if file_info["file_id"] == file_id:
            file_info["uploaded"] = True
            break
    
    session["files_info"] = files_info
    return {"status": "success"}

@app.route("/combine")
def combine():
    if "files_info" not in session or not session["files_info"]:
        return "No files to combine.", 400

    # 各ファイルのバイトデータをメモリストリームとして取得
    # booklet.pyがファイルパスではなくメモリオブジェクトを扱えるように対応
    input_files_streams = [BytesIO(get_file_bytes(item)) for item in session["files_info"]]
    
    # 出力ファイルを一時的にローカル（GAE環境では/tmp）に保存
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

    # 全PDFを結合してメモリ上に一つのPDFオブジェクトとして保持
    combined_pdf = PdfWriter()
    for file_info in session.get("files_info", []):
        pdf_bytes = get_file_bytes(file_info)
        reader = PdfReader(BytesIO(pdf_bytes))
        for page in reader.pages:
            combined_pdf.add_page(page)
    
    # 曲ごとに分割・加工処理を実行
    filename_list = []
    names_and_ranges_info = data.get("songs", [])
    initial_number = int(data.get("initial_number", 1))

    prefix_pairing = {"mixed": "混声", "female": "女声", "male": "男声"}
    converted_prefix = prefix_pairing.get(data.get("prefix"), "")

    for info in names_and_ranges_info:
        # 曲番号、曲名、ページ範囲を取得
        number = info["number"]
        name = info["name"]
        start_page = int(info["start"]) - initial_number
        end_page = int(info["end"]) - initial_number

        # 指定範囲のページを抽出してB5サイズに変換
        tmp_writer = PdfWriter()
        for i in range(start_page, end_page + 1):
            if 0 <= i < len(combined_pdf.pages):
                page = combined_pdf.pages[i]
                page = convert_to_B5(page)  # ページオブジェクトを直接操作
                tmp_writer.add_page(page)
        
        # 加工したPDFを一時フォルダに保存
        filename = f"{converted_prefix}{number:02d}{name}.pdf"
        output_path = os.path.join(TMP_PATH, filename)
        filename_list.append(filename)
        with open(output_path, "wb") as f:
            tmp_writer.write(f)

    # ZIPファイルを作成してダウンロード用に準備
    zip_filename = f"{converted_prefix}song_pdfs.zip"
    zip_output_path = os.path.join(TMP_PATH, zip_filename)

    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for filename in filename_list:
            path = os.path.join(TMP_PATH, filename)
            zf.write(path, arcname=filename)
            os.remove(path)  # ZIPに追加後、一時ファイルを削除

    session["ZIP_FILENAME"] = zip_filename
    session["ZIP_OUTPUT_PATH"] = zip_output_path
    return redirect(url_for("zip_download"))

# =============================================================================
# その他のルート（削除、ダウンロード、順序変更）
# =============================================================================

@app.route("/clear")
def clear():
    if "files_info" in session:
        for item in session["files_info"]:
            delete_file(item)
        session["files_info"] = []
    return redirect(url_for("index"))

@app.route("/delete")
def delete():
    if "files_info" not in session:
        return redirect(url_for("index"))
    
    files_info = session["files_info"]
    
    # 削除対象をファイル名で特定
    # 注意: 同じファイル名が複数ある場合、すべて削除される
    files_to_keep = []
    for item in files_info:
        if item["file_name"] == "バビロン.pdf":
            delete_file(item)  # GCS/ローカルからファイルを削除
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
    
    # ファイル名をキーとしたマップを作成
    map_by_name = {item["file_name"]: item for item in files_info}
    
    # 順番データに存在するファイルのみで新しいリストを作成
    files_info_new = [map_by_name[name] for name in order if name in map_by_name]
    
    session["files_info"] = files_info_new
    # 画面遷移を伴わないのでリダイレクトではなく成功応答を返
    return {"status": "success"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)