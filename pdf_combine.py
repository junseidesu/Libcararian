import os
from pypdf import PdfWriter, PdfReader
from main import UPLOAD_FOLDER
import io

B5_size=(515.9,728.5)

def pdf_combine(files, scale_to_B5=True):
    writer=PdfWriter()
    
    #全てのファイルの全てのページをwriterに結合
    for file in files:
        reader=PdfReader(file)
        for page in reader.pages:
            if scale_to_B5:
                page.transfer_rotation_to_content()
                page.scale_to(B5_size[0],B5_size[1])
                page.cropbox=page.mediabox

            writer.add_page(page)
            
    with open("combined.pdf","wb") as f:
        writer.write(f)
        print("結合に成功しました")
    
    
files=[os.path.join(UPLOAD_FOLDER,file) for file in os.listdir(UPLOAD_FOLDER) if file.lower().endswith(".pdf")]

if __name__=="__main__":
    pdf_combine(files)

    