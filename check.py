from pypdf import PdfReader

reader=PdfReader("混声01aaa.pdf")
for page in reader.pages:
    print(page.cropbox)