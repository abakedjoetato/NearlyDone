document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('upload-form');
    const uploadBtn = document.getElementById('upload-btn');
    const uploadSpinner = document.getElementById('upload-spinner');
    const uploadResult = document.getElementById('upload-result');
    const uploadSuccess = document.getElementById('upload-success');
    const uploadError = document.getElementById('upload-error');
    const errorMessage = document.getElementById('error-message');
    
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Show spinner
        uploadBtn.disabled = true;
        uploadSpinner.classList.remove('d-none');
        uploadResult.classList.add('d-none');
        uploadSuccess.classList.add('d-none');
        uploadError.classList.add('d-none');
        
        // Get form data
        const formData = new FormData(uploadForm);
        
        // Send request
        fetch('/upload', {
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            // Hide spinner
            uploadBtn.disabled = false;
            uploadSpinner.classList.add('d-none');
            uploadResult.classList.remove('d-none');
            
            if (data.success) {
                // Show success message
                uploadSuccess.classList.remove('d-none');
                
                // Log information about the uploaded bot
                console.log('Main files:', data.main_files);
                console.log('Python files:', data.python_files);
            } else {
                // Show error message
                uploadError.classList.remove('d-none');
                errorMessage.textContent = data.error || 'An unknown error occurred';
            }
        })
        .catch(error => {
            // Hide spinner
            uploadBtn.disabled = false;
            uploadSpinner.classList.add('d-none');
            uploadResult.classList.remove('d-none');
            
            // Show error message
            uploadError.classList.remove('d-none');
            errorMessage.textContent = 'Network error: ' + error.message;
        });
    });
});
