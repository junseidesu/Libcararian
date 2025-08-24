function AutoUpload(){
    const fileInput=document.querySelector('input[type="file"][name="file"]')
    const form=document.querySelector('form[id="upload"]')
    const loadingIndicator = document.getElementById('loading-indicator');

    fileInput.addEventListener('change',async function(){
        console.log(this.files);
        if(this.files.length>0){
            loadingIndicator.style.display = 'block'
            
            if(IS_GAE){
                const fileDataList=Array.from(fileInput.files)
                try{
                    for(const file of fileDataList){
                        const urlResponse=await fetch("/generate_signed_url", {
                            method: 'POST',
                            headers:{
                                'Content-Type': 'application/json'
                            },
                            body:JSON.stringify({
                                file_name:file.name,
                                file_type:file.type
                            })
                        });
                        console.log(urlResponse);
                        if(!urlResponse.ok){
                            alert(`URLの取得に失敗：${file.name}ほんま？`);
                            console.error(`URL取得エラー：${urlResponse.statusText}`);
                            continue;
                        }
                        const response=await urlResponse.json();
                        const uploadResponse=await fetch(response.signed_url, {
                            method: 'PUT',
                            headers: {
                                'Content-Type': file.type,
                            },
                            body:file
                        });
                        if(!uploadResponse.ok){
                            alert(`ファイルのアップロードに失敗：${file.name}`);
                            continue;
                        }

                        await fetch("/confirm_upload", {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({
                                file_id: response.file_id
                            })
                        });
                    }
                    window.location.reload();
                }catch(error){
                    alert(`エラー発生：${error.message}`);
                }
            }else{
                form.submit();
            }
            
        }
    });
    setupFileListSortable();
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
    const fileList= document.getElementById('file-list');
    const fileListItems =Array.from(fileList.children);
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

// New function for drag and drop
function setupDragAndDrop() {
    const uploadArea = document.querySelector('.upload-area');
    const fileInput = document.querySelector('input[type="file"][name="file"]');
    const uploadForm = document.getElementById('upload');

    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false); // For preventing outside the area
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Highlight drop area when item is dragged over it
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.add('highlight'), false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => uploadArea.classList.remove('highlight'), false);
    });

    // Handle dropped files
    uploadArea.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        // Assign the dropped files to the file input
        fileInput.files = files;

        // Programmatically submit the form
        uploadForm.submit();
    }
}

function setupFileListSortable() {
    const fileList = document.getElementById('file-list');
    
    // Sortable.jsを使用してファイルリストをドラッグ＆ドロップ可能にする
    new Sortable(fileList, {
        animation: 150,
        onEnd: function (evt) {
            // ドラッグ＆ドロップ後の処理
            const orderedFiles =Array.from(fileList.children).map(li => li.dataset.fileName);
            fetch('/update_file_order',{
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ order: orderedFiles })
            })
        }
    });
}



document.addEventListener('DOMContentLoaded', function() {
    AutoUpload();
    pdfPreview();
    setupDialog();
    setupRangeButtons();
    setupCombineBySong(); // ここで呼び出す
    setupDragAndDrop();
    setupFileListSortable(); // ファイルリストのソート機能をセットアップ
});