// Function to force Android Download via Vercel Proxy
function forceAndroidDownload(filename, dataUri) {
    // Create a hidden form
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/download'; // Calls your new Python script
    form.style.display = 'none';

    // Add Filename
    const nameInput = document.createElement('input');
    nameInput.name = 'filename';
    nameInput.value = filename;
    form.appendChild(nameInput);

    // Add File Data
    const dataInput = document.createElement('input');
    dataInput.name = 'fileData';
    dataInput.value = dataUri;
    form.appendChild(dataInput);

    // Submit and Cleanup
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
}
