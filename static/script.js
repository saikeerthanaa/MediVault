// 1. CLOCK FUNCTIONALITY
function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('date').innerText = now.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}
setInterval(updateClock, 1000);
updateClock();

// 2. DOM ELEMENTS
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const loadingArea = document.getElementById('loadingArea');
const resultCard = document.getElementById('resultCard');

// 3. CLICK TO UPLOAD
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleUpload(e.target.files[0]);
});

// 4. REAL DRAG & DROP LOGIC
dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = "var(--accent)"; // Glows when dragging over
    dropZone.style.background = "rgba(108, 92, 231, 0.1)";
});

dropZone.addEventListener('dragleave', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = "rgba(255,255,255,0.2)"; // Resets when cursor leaves
    dropZone.style.background = "rgba(0,0,0,0.1)";
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.style.borderColor = "rgba(255,255,255,0.2)"; 
    dropZone.style.background = "rgba(0,0,0,0.1)";
    
    if (e.dataTransfer.files.length > 0) {
        handleUpload(e.dataTransfer.files[0]);
    }
});

// 5. THE API INTEGRATION
async function handleUpload(file) {
    // Hide upload box, show loading spinner
    dropZone.classList.add('hidden');
    loadingArea.classList.remove('hidden');

    // Package the file to send to the Python backend
    const formData = new FormData();
    formData.append('file', file); // 'file' is the exact name the Python script will look for

    try {
        // Send to your backend API endpoint 
        // NOTE: Make sure your backend team names their route '/upload_scan'
        const response = await fetch('/upload_scan', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            throw new Error("Server rejected the file.");
        }

        // Wait for AWS Textract and the database to finish, then get the results back
        const data = await response.json();
        
        // Hide loading, show the success card
        loadingArea.classList.add('hidden');
        resultCard.classList.remove('hidden');
        
        // Populate the UI with real data from the backend
        document.getElementById('pName').innerText = "Detected: " + (data.patient_name || "Unknown Patient");
        
        // Take the long security hash and shorten it so it fits perfectly on the card
        const hash = data.file_hash || "0x_error_generating_hash";
        const shortHash = hash.substring(0, 6) + "..." + hash.substring(hash.length - 4);
        document.getElementById('fileHash').innerText = shortHash + " (Immutable)";

    } catch (error) {
        console.error("Upload failed:", error);
        
        // If it fails, hide the loader and show the upload box again
        loadingArea.classList.add('hidden');
        dropZone.classList.remove('hidden');
        alert("Upload failed! Make sure the Python backend is running.");
    }
}
