from flask import Flask, render_template, request, send_from_directory, Response, session, redirect, url_for
import os
from io import BytesIO
import uuid
from pypdf import PdfReader, PdfWriter
from flask_session import Session
from booklet import change_to_booklet

app = Flask(__name__)
app.secret_key="20041007"
app.config["UPLOAD_FOLDER"]=os.path.join("/tmp", "uploads")
app.config["EDITED_FOLDER"]=os.path.join("/tmp","edited")
if not os.path.exists("uploads"):
    os.mkdir("uploads")
if not os.path.exists("edited"):
    os.mkdir("edited")

# セッションの永続化を無効にする（ブラウザを閉じるとセッションが終了）
app.config["SESSION_PERMANENT"] = False
# セッションのタイプをファイルシステムに設定（プロダクションではRedisやDBが推奨されます）
app.config["SESSION_TYPE"] = "filesystem"
# ファイルシステムセッションを保存するディレクトリ
app.config["SESSION_FILE_DIR"] = os.path.join("/tmp","flask_session")
# セッション保存ディレクトリが存在しない場合は作成
if not os.path.exists(app.config["SESSION_FILE_DIR"]):
    os.makedirs(app.config["SESSION_FILE_DIR"])

Session(app)

@app.route("/")
def index():
    files_info=session.get("files_info",default=[])
    file_names=[item["file_name"] for item in files_info]
    return render_template("index.html", file_names=file_names)

@app.route("/upload", methods=["POST"])
def upload_file():
    #requestオブジェクトから"file"をリストで取得
    files=request.files.getlist("file")
    files_info=session.get("files_info",default=[])
    """
    files_infoの構造
    files_info=[{
        "file_id"=id(各ファイルのid)
        "file_name":ファイル名
        "storedfile_name":ファイルの保存名
        "storedfile_path":ファイルの保存パス
    }]
    """
    for file in files:
        #fileにuniqueなファイル名を付けてuploadsに保存
        storedfile_name=str(uuid.uuid4())+"_"+file.filename
        storedfile_path=os.path.join(app.config["UPLOAD_FOLDER"],storedfile_name)
        file.save(storedfile_path)

        files_info.append({
            "file_id":uuid.uuid4(),
            "file_name":file.filename,
            "storedfile_name":storedfile_name,
            "storedfile_path":storedfile_path
        })
    #sessionへの保存
    session["files_info"]=files_info

    return redirect(url_for("index"))
    

@app.route("/delete")
def delete():
    files_info=session.get("files_info",default=[])
    target_indexies=[index for index,item in enumerate(files_info) if item["file_name"]=="バビロン.pdf"]
    for index in target_indexies:
        os.remove(files_info[index]["storedfile_path"])
        files_info.pop(index)
    session["files_info"]=files_info
    return redirect(url_for("index"))

@app.route("/clear")
def clear():
    files_info=session.get("files_info",default=[])
    for item in files_info:
        os.remove(item["storedfile_path"])
    files_info.clear()
    session["files_info"]=files_info
    return redirect(url_for("index"))

@app.route("/combine")
def combine():
    files_info=session.get("files_info",default=[])
    #change_to_booklet(input_files, output_path, center_gap_mm=0, unnumbering_page=0,start_page=1, isBooklet=True)
    input_files=[item["storedfile_path"] for item in files_info]
    output_path="edited\combine.pdf"
    center_gap_mm=20
    isNumbering=True if request.args.get("isNumbering")=="numbering" else False
    isBooklet=True if request.args.get("isBooklet")=="booklet" else False
    unnmbering_page=int(request.args.get("no-number-pages"))
    start_page=int(request.args.get("start-number"))
    change_to_booklet(
        input_files=input_files,
        output_path=output_path,
        center_gap_mm=center_gap_mm,
        isNumbering=isNumbering,
        unnumbering_page=unnmbering_page,
        start_page=start_page,
        isBooklet=isBooklet
    )
    return send_from_directory(
        "edited",
        "combine.pdf",
        as_attachment=True,
        mimetype="application/pdf",
        download_name="結合ファイル.pdf"
    )

@app.route("/preview/<filename>")
def preview(filename):
    file_info=session.get("files_info",default=[])
    for item in file_info:
        if item["file_name"] == filename:
            return send_from_directory(
                app.config["UPLOAD_FOLDER"],
                item["storedfile_name"],
                as_attachment=False,
                mimetype="application/pdf",
            )
    return "File not found", 404

@app.route("/combine_by_song", methods=["POST"])
def combine_by_song():
    data = request.get_json()
    print(data)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)