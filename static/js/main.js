function AutoUpload(){
    const fileInput=document.querySelector('input[type="file"][name="file"]')
    const form=document.querySelector('form[id="upload"]')
    fileInput.addEventListener('change',function(){
        if(this.files.length>0){
            form.submit();
        }
    });
}

// Global variables for PDF preview
let currentPdf = null;
let currentPageNum = 0; // 0-indexed page number
let totalPages = 0;

function updatePageControls() {
    const prevButton = document.getElementById('prevPage');
    const nextButton = document.getElementById('nextPage');
    const pageNumberDisplay = document.getElementById('pageNumberDisplay');

    if (currentPdf) {
        prevButton.disabled = currentPageNum <= 0;
        nextButton.disabled = currentPageNum >= totalPages - 1;
        pageNumberDisplay.textContent = `ページ ${currentPageNum + 1} / ${totalPages}`;
    } else {
        prevButton.disabled = true;
        nextButton.disabled = true;
        pageNumberDisplay.textContent = 'ページ - / -';
    }
}

async function renderPage(pageNum) {
    if (!currentPdf || pageNum < 0 || pageNum >= totalPages) {
        console.error('Invalid page number or PDF not loaded.');
        return;
    }

    currentPageNum = pageNum;
    updatePageControls();

    const canvas = document.getElementById('preview-canvas');
    const context = canvas.getContext('2d');

    // PDF.jsのページ番号は1-indexedなので、currentPageNumに1を足します
    const page = await currentPdf.getPage(currentPageNum + 1);
    const viewport = page.getViewport({ scale: 1 });

    // プレビューの幅に合わせてキャンバスのサイズとスケールを調整
    const desiredWidth = 900; // 例: プレビューの望ましい幅
    const scale = desiredWidth / viewport.width;
    const scaledViewport = page.getViewport({ scale: scale});

    canvas.width = scaledViewport.width;
    canvas.height = scaledViewport.height;

    const renderContext = {
        canvasContext: context,
        viewport: scaledViewport
    };
    await page.render(renderContext).promise;
}



function pdfPreview(){
    console.log('PDF Preview Initialized');
    const fileListItems = document.querySelectorAll('.file-list li');
    
    // Set worker source for PDF.js
    pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.10.377/pdf.worker.min.js';

    fileListItems.forEach(item => {
        item.addEventListener('click', async function(event){
            const targetLi = this;
            const fileName = targetLi.dataset.fileName;
            const pdfUrl = `/preview/${fileName}`;

            try{
                // Load the PDF document
                const loadingTask = pdfjsLib.getDocument(pdfUrl);
                currentPdf = await loadingTask.promise;
                totalPages = currentPdf.numPages;
                
                // Render the first page initially
                await renderPage(0); // 最初のページ (0-indexed) をレンダリング

            }catch(error){
                console.error('Error loading PDF:', error);
                currentPdf = null;
                totalPages = 0;
                updatePageControls();
                const canvas = document.getElementById('preview-canvas');
                const context = canvas.getContext('2d');
                context.clearRect(0, 0, canvas.width, canvas.height); // エラー時にキャンバスをクリア
            }
        });
    });

    // Add event listeners for navigation buttons
    document.getElementById('prevPage').addEventListener('click', () => {
        if (currentPageNum > 0) {
            renderPage(currentPageNum - 1);
        }
    });

    document.getElementById('nextPage').addEventListener('click', () => {
        if (currentPageNum < totalPages - 1) {
            renderPage(currentPageNum + 1);
        }
    });

    updatePageControls(); // 初期ロード時にボタンの状態を更新
}

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
function setupCombineBySong(){
    const submitButton = document.getElementById('combineBySong');
    
    submitButton.addEventListener('click', async function(event) {
        event.preventDefault()
        

        // フォームデータを収集
        const prefix = document.getElementById('prefix').value;
        const initialNumber = parseInt(document.querySelector('input[name="initial-number"]').value) || 1;
        
        // 曲の情報を収集
        const songs = [];
        const rangeItems = document.querySelectorAll('.range-item');
        
        rangeItems.forEach(item => {
            const songNumber = parseInt(item.querySelector('input[name="song-number"]').value);
            const songName = item.querySelector('input[name="song-name"]').value;
            const startNumber = parseInt(item.querySelector('input[name="start-number"]').value);
            const endNumber = parseInt(item.querySelector('input[name="end-number"]').value);
            
            if (songName && startNumber && endNumber) {
                songs.push({
                    number:songNumber,
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
        
        const myDialog = document.getElementById('myDialog');
        myDialog.close();
        window.location.href=response.url;
    });
}

document.addEventListener('DOMContentLoaded', function() {
    AutoUpload();
    pdfPreview();
    setupDialog();
    setupRangeButtons();
    setupCombineBySong(); // ここで呼び出す
});