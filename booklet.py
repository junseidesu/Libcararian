from pypdf import *
import io
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import B5

#サイズ定義
B4_size=(1031.8,728.5)
B5_size=(515.9,728.5)

#1pt=0.35mm
margin_x=15
margin_y=10
box_width=30
box_height=25

def convert_to_B5(page):
    # 元のページの回転角度を取得
    original_rotation = page.rotation

    # ページの回転をリセット
    if original_rotation != 0:
        page.rotate(-original_rotation)

    # ページをB5サイズにスケーリング
    page.scale_to(width=B5_size[0], height=B5_size[1])

    # 必要であれば再度回転させる
    # ただし、コンテンツに直接適用するわけではない
    if original_rotation != 0:
        page.rotate(original_rotation)
        
    print(f"After scaling: {page.mediabox.width} x {page.mediabox.height}")
    return page

def change_to_booklet(
        input_files,
        output_path,
        center_gap_mm=0,
        isNumbering=True,
        unnumbering_page=0,
        start_page=1,
        isBooklet=True
    ):

    #中間の幅を指定、B5サイズからの比率に変換
    center_gap_pt=center_gap_mm*2.83

    #インスタンス生成、writer：結合ファイルを継承し編集可能　booklet：作成するファイル
    writer=PdfWriter()
    booklet=PdfWriter()

    for file in input_files:
        reader=PdfReader(file)
        for page in reader.pages:
            writer.add_page(page)

    #元ファイルのページ数
    num_pages=len(writer.pages)


    #writerの各ページをB5にスケーリング
    for page in writer.pages:
        page=convert_to_B5(page)


    if isNumbering:
        numbered_writer = PdfWriter()
        # writerの各ページにページ番号を追加
        for i, page in enumerate(writer.pages):
            if i < unnumbering_page:
                numbered_writer.add_page(page)
                continue

            packet = io.BytesIO()
            # reportlabで新しいPDF（キャンバス）を作成
            can = canvas.Canvas(packet, pagesize=B5)

            page_width, page_height = B5 # B5サイズをptで取得

            page_number_text = str(i + start_page - unnumbering_page)

            # ページ番号の位置を左右で変える
            if i % 2 == 0:  # 右ページ
                x = page_width - margin_x+3
                can.drawString(x, margin_y, page_number_text)
            else:  # 左ページ
                x = margin_x
                can.drawString(x, margin_y, page_number_text)
            
            can.save()

            # packetの先頭にシーク
            packet.seek(0)
            
            # ページ番号が書かれたPDFを読み込む
            number_pdf = PdfReader(packet)
            number_page = number_pdf.pages[0]

            # 元のページにページ番号のページを重ねる
            page.merge_page(number_page)
            numbered_writer.add_page(page)

    else:
        numbered_writer = writer
    #小冊子に出来るように4の倍数ページになるまで白紙のページを追加
    
            
            
    #並べ替えの順番を作成
    booklet_order=[]

    if isBooklet:
        if num_pages%4==0:
            pass
        else:
            while len(numbered_writer.pages)%4!=0:
                numbered_writer.add_blank_page(width=B5_size[0],height=B5_size[1])
        
        # 白紙ページ追加後の正確なページ数を取得
        booklet_pages=len(numbered_writer.pages)
                
        for i in range(0,booklet_pages//2,2):
            booklet_order.append((booklet_pages-1-i,i))
            booklet_order.append((i+1,booklet_pages-1-(i+1)))

        #for内で使うbookletのページ数
        #for内で使うbookletのページ数
        current_booklet_page=0

        # 各ページの配置可能幅を計算
        available_width_per_page = (B4_size[0] - center_gap_pt) / 2
        scale_factor = available_width_per_page / B5_size[0]

        for pair in booklet_order:
            leftpage=numbered_writer.pages[pair[0]]
            rightpage=numbered_writer.pages[pair[1]]

            #スケーリング（間隔を考慮してページを縮小）
            leftpage.scale(sx=scale_factor, sy=1)
            rightpage.scale(sx=scale_factor, sy=1)

            #新しい空白ページを作成
            booklet.add_blank_page(width=B4_size[0], height=B4_size[1])

            #左右に貼り付け
            booklet.pages[current_booklet_page].merge_page(leftpage)
            booklet.pages[current_booklet_page].merge_translated_page(
                rightpage, 
                tx=available_width_per_page + center_gap_pt,  # 左ページ幅 + 間隔
                ty=0
            )
            
            current_booklet_page+=1
    else:
        booklet=numbered_writer
    #ファイル保存
    with open(output_path,"wb") as output_file:
        booklet.write(output_file)
        print("一括結合に成功")