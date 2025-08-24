document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('incidentReportForm');
    const mediaUploadBox = document.getElementById('mediaUploadBox');
    const fileInput = document.getElementById('incidentMedia');
    const previewContainer = document.getElementById('mediaPreviewContainer');
    const reporterType = document.getElementById('reporter_type');
    const reporterInfoContainer = document.getElementById('reporterInfoContainer');

    // Handle file uploads and previews
    mediaUploadBox.addEventListener('click', () => fileInput.click());
    
    mediaUploadBox.addEventListener('dragover', (e) => {
        e.preventDefault();
        mediaUploadBox.classList.add('border-blue-500', 'bg-blue-50');
    });
    
    mediaUploadBox.addEventListener('dragleave', () => {
        mediaUploadBox.classList.remove('border-blue-500', 'bg-blue-50');
    });
    
    mediaUploadBox.addEventListener('drop', (e) => {
        e.preventDefault();
        mediaUploadBox.classList.remove('border-blue-500', 'bg-blue-50');
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            updateFilePreviews();
        }
    });
    
    fileInput.addEventListener('change', updateFilePreviews);
    
    // Show/hide reporter info based on selection
    reporterType.addEventListener('change', function() {
        if (this.value === 'public' || this.value === 'other') {
            reporterInfoContainer.classList.remove('hidden');
        } else {
            reporterInfoContainer.classList.add('hidden');
        }
    });
    
    function updateFilePreviews() {
        previewContainer.innerHTML = '';
        if (fileInput.files.length > 5) {
            alert('Maximum 5 files allowed');
            fileInput.value = '';
            return;
        }
        
        Array.from(fileInput.files).forEach(file => {
            const fileDiv = document.createElement('div');
            fileDiv.className = 'flex items-center p-2 border rounded bg-slate-50';
            
            const fileName = document.createElement('span');
            fileName.className = 'text-sm text-slate-700 ml-2';
            fileName.textContent = file.name;
            
            fileDiv.appendChild(fileName);
            previewContainer.appendChild(fileDiv);
        });
    }
});