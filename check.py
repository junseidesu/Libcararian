from pypdf import PdfReader

reader=PdfReader("混声01aaa.pdf")
for page in reader.pages:
    print(page.cropbox)

def convert_to_B5(page):
    page.transfer_rotation_to_content()
    page_width=page.mediabox.width
    page_height=page.mediabox.height
    sx=B5_size[0]/page_width
    sy=B5_size[1]/page_height
    page.scale(sx=sx, sy=sy)
    return page