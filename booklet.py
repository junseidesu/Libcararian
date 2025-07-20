from pypdf import *
import fitz
import io

#サイズ定義
B4_size=(1031.8,728.5)
B5_size=(515.9,728.5)

#1pt=0.35mm
margin_x=15
margin_y=5
box_width=30
box_height=25

def convert_to_B5(page):
    page.transfer_rotation_to_content()
    page_width=page.mediabox.width
    page_height=page.mediabox.height
    sx=B5_size[0]/page_width
    sy=B5_size[1]/page_height
    page.scale(sx=sx, sy=sy)
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
        temp_file_stream=io.BytesIO()
        writer.write(temp_file_stream)
        temp_file_stream.seek(0)

        no_number_conbined=fitz.open("pdf", temp_file_stream)




        for i in range(0,num_pages):
            if i<unnumbering_page:
                continue
            else:
                no_number_page=no_number_conbined.load_page(i)
                no_number_page_width=B5_size[0]
                no_number_page_height=B5_size[1]



                if i%2==0:
                    x0=no_number_page_width-margin_x-box_width+10
                    y0=no_number_page_height-(margin_y+box_height)
                    x1=no_number_page_width-margin_x+10
                    y1=no_number_page_height-margin_y

                    text_rect=fitz.Rect(x0,y0,x1,y1)

                    no_number_page.insert_textbox(
                        text_rect,
                        str(i+start_page-unnumbering_page),
                        fontsize=12,
                        align="right",
                        fontname="helv"
                    )

                else:
                    x0=margin_x
                    y0=no_number_page_height-(margin_y+box_height)
                    x1=margin_x+box_width
                    y1=no_number_page_height-margin_y

                    text_rect=fitz.Rect(x0,y0,x1,y1)

                    no_number_page.insert_textbox(
                        text_rect,
                        str(i+start_page-unnumbering_page),
                        fontsize=12,
                        align="left",
                        fontname="helv"
                    )


        numbered_conbined_bytes=no_number_conbined.tobytes()
        no_number_conbined.close()

        numbered_writer=PdfWriter(io.BytesIO(numbered_conbined_bytes))
    else:
        numbered_writer=writer
    #小冊子に出来るように4の倍数ページになるまで白紙のページを追加
    if num_pages%4==0:
        pass
    else:
        while len(numbered_writer.pages)%4!=0:
            numbered_writer.add_blank_page(width=B5_size[0],height=B5_size[1])
            
            
    #並べ替えの順番を作成
    booklet_order=[]
    booklet_pages=len(numbered_writer.pages)

    if isBooklet:
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