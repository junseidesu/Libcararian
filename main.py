from flask import Flask, render_template, request, send_from_directory, Response, session, redirect, url_for, send_file
import os
from io import BytesIO
import uuid
from pypdf import PdfReader, PdfWriter
from flask_session import Session
from booklet import change_to_booklet, convert_to_B5
import zipfile
from dotenv import load_dotenv

load_dotenv()  # .envファイルの読み込み
TMP_PATH = os.getenv("TMP_PATH", "tmp")  # .envからTMP_PATHを取得、デフォルトは"tmp"

app = Flask(__name__)
app.secret_key="20041007"
app.config["UPLOAD_FOLDER"]=os.path.join(TMP_PATH, "uploads")
app.config["EDITED_FOLDER"]=os.path.join(TMP_PATH,"edited")
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = os.path.join(TMP_PATH,"flask_session")

for folder in [app.config["UPLOAD_FOLDER"], app.config["EDITED_FOLDER"], app.config["SESSION_FILE_DIR"]]:
    if not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)


Session(app)

@app.route("/")
def index():
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]

    file_names=[item["file_name"] for item in files_info]
    return render_template("index.html", file_names=file_names)

@app.route("/upload", methods=["POST"])
def upload_file():
    #requestオブジェクトから"file"をリストで取得
    files=request.files.getlist("file")
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]
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
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]
    
    target_indexies=[index for index,item in enumerate(files_info) if item["file_name"]=="バビロン.pdf"]
    for index in target_indexies:
        os.remove(files_info[index]["storedfile_path"])
        files_info.pop(index)
    session["files_info"]=files_info
    return redirect(url_for("index"))

@app.route("/clear")
def clear():
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]

    for item in files_info:
        os.remove(item["storedfile_path"])
    files_info.clear()
    session["files_info"]=files_info
    return redirect(url_for("index"))

@app.route("/combine")
def combine():
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]
    
    #change_to_booklet(input_files, output_path, center_gap_mm=0, unnumbering_page=0,start_page=1, isBooklet=True)
    input_files=[item["storedfile_path"] for item in files_info]
    output_path=os.path.join(app.config["EDITED_FOLDER"],"combine.pdf")
    center_gap_mm=20
    isNumbering=True if request.args.get("isNumbering")=="numbering" else False
    isBooklet=True if request.args.get("isBooklet")=="booklet" else False
    unnumbering_page=int(request.args.get("no-number-pages"))
    start_page=int(request.args.get("start-number"))
    change_to_booklet(
        input_files=input_files,
        output_path=output_path,
        center_gap_mm=center_gap_mm,
        isNumbering=isNumbering,
        unnumbering_page=unnumbering_page,
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
    if "files_info" in session:
        files_info=session["files_info"]
    else:
        files_info=[]
    
    for item in files_info:
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
    if data is None:
        return "Invalid JSON data", 400
    names_and_ranges_info=data["songs"]
    prefix=data["prefix"]
    prefix_pairing={
        "mixed":"混声",
        "female":"女声",
        "male":"男声"
    }
    converted_prefix=prefix_pairing.get(prefix, "")  # デフォルトはそのままのprefixを使用



    initial_number=int(data["initial_number"])
    files_info=session["files_info"]
    combined_pdf=PdfWriter()
    for file_info in files_info:
        path=file_info["storedfile_path"]
        reader=PdfReader(path)
        for page in reader.pages:
            combined_pdf.add_page(page)
    
    filename_list=[]

    for name_and_range_info in names_and_ranges_info:
        number=name_and_range_info["number"]
        name=name_and_range_info["name"]
        start_page=int(name_and_range_info["start"])
        end_page=int(name_and_range_info["end"])

        start_page_red=start_page-initial_number
        end_page_red=end_page-initial_number

        tmp_writer=PdfWriter()
        for i in range(start_page_red,end_page_red+1):
            page=combined_pdf.pages[i]
            page=convert_to_B5(page)
            tmp_writer.add_page(page)
        
        filename=f"{converted_prefix}{number:02d}{name}.pdf"
        output_path=os.path.join(app.config["EDITED_FOLDER"],filename)
        filename_list.append(filename)
        with open(output_path,"wb") as f:
            tmp_writer.write(f)
    
    zip_filename=f"{converted_prefix}song_pdfs.zip"
    zip_output_path=os.path.join(app.config["EDITED_FOLDER"],zip_filename)

    with zipfile.ZipFile(zip_output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # 例: EDITED_FOLDER 内のPDFファイルをすべてZIPに追加
        # 実際には、ZIPに含めたいファイルのパスを正確に指定する必要があります
        for filename in filename_list:
            path=os.path.join(app.config["EDITED_FOLDER"],filename)
            zf.write(path, arcname=filename) # ZIPファイル内のパスと名前

    session["ZIP_FILENAME"]=zip_filename
    session["ZIP_OUTPUT_PATH"]=zip_output_path
    return redirect(url_for("zip_download"))

@app.route("/zip_download")
def zip_download():
    zip_filename=session["ZIP_FILENAME"]
    zip_output_path=session["ZIP_OUTPUT_PATH"]
    return send_file(
        zip_output_path,
        mimetype='application/zip', # ZIPファイルのMIMEタイプ
        as_attachment=True,         # ダウンロードを促す
        download_name=zip_filename    # クライアントに提案するファイル名
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)