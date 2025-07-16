function AutoUpload(){
    const fileInput=document.querySelector('input[type="file"][name="file"]')
    const form=document.querySelector('form[id="upload"]')
    fileInput.addEventListener('change',function(){
        if(this.files.length>0){
            form.submit();
        }
    });
}
AutoUpload();

function pdfPreview(){
    console.log('PDF Preview Initialized');
    const fileListItems = document.querySelectorAll('.file-list li');
    const canvas=document.getElementById('preview-canvas');
    const context=canvas.getContext('2d');
    const previewPanel = document.getElementById('preview-panel');
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.10.377/pdf.worker.min.js';
    fileListItems.forEach(item =>{
        item.addEventListener('click', async function(event){
            const targetLi=this;
            const fileName=targetLi.dataset.fileName;
            const pdfUrl=`/preview/${fileName}`;

            try{
                const loadingTask=pdfjsLib.getDocument(pdfUrl);
                const pdf=await loadingTask.promise;

                const page=await pdf.getPage(1);
                const viewport=page.getViewport({scale:1});
                canvas.width=viewport.width;
                canvas.height=viewport.height;

                const renderContext={
                    canvasContext:context,
                    viewport:viewport
                };
                await page.render(renderContext).promise;

            }catch(error){
                console.error('Error loading PDF:', error);
            }
        })
    })
}

pdfPreview();


function setupDialog(){
    const openButton = document.getElementById('openButton');
    const closeButton = document.getElementById('closeButton');
    const myDialog = document.getElementById('myDialog');

    // 「フォームを開く」ボタンが押されたら、ウィンドウを表示
    openButton.addEventListener('click', () => {
        myDialog.showModal(); // これだけで背景が暗くなり、中央に表示される
    });

    // 「閉じる」ボタンが押されたら、ウィンドウを閉じる
    closeButton.addEventListener('click', () => {
        myDialog.close();
    });
}

setupDialog();

function setupRangeButtons() {
    const gapArea=document.getElementById('gapArea');
    const panel = document.querySelector('.range-panel');
    const template = document.getElementById('range-template');
    gapArea.addEventListener('click', function(event){
        // 「追加ボタン」がクリックされた場合
        if (event.target.classList.contains('add-range-btn')) {
            const clone = template.content.cloneNode(true);
            panel.appendChild(clone);
        }
        // 「削除ボタン」がクリックされた場合
        if ((event.target.classList.contains('delete-range-btn'))&&document.querySelectorAll('.range-item').length>1) {
            event.target.closest('.range-item').remove();
        }
    });
}
setupRangeButtons();

function setupCombineBySong(){
    const submitButton = document.getElementById('combineBySong');
    
    submitButton.addEventListener('click', async function() {

        

        // フォームデータを収集
        const prefix = document.getElementById('prefix').value;
        const initialNumber = parseInt(document.getElementById('initial-number').value) || 1;
        
        // 曲の情報を収集
        const songs = [];
        const rangeItems = document.querySelectorAll('.range-item');
        
        rangeItems.forEach(item => {
            const songName = item.querySelector('.song-name').value;
            const startNumber = parseInt(item.querySelector('.start-number').value);
            const endNumber = parseInt(item.querySelector('.end-number').value);
            
            if (songName && startNumber && endNumber) {
                songs.push({
                    name: songName,
                    start: startNumber,
                    end: endNumber
                });
            }
        });
        
        // JSONデータを作成
        const requestData = {
            prefix: prefix,
            initial_number: initialNumber,
            songs: songs
        };
        const response = await fetch('/combine_by_song', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(requestData)
        });
    });
}
setupCombineBySong();