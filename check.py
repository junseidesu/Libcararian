from pypdf import PdfReader

reader=PdfReader("combined.pdf")
for page in reader.pages:
    print(page.cropbox)