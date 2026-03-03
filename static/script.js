// 1. CLOCK FUNCTIONALITY
function updateClock() {
    const now = new Date();
    document.getElementById('clock').innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    document.getElementById('date').innerText = now.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' });
}
setInterval(updateClock, 1000);
updateClock();

// 2. UPLOAD LOGIC
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const loadingArea = document.getElementById('loadingArea');
const resultCard = document.getElementById('resultCard');

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) handleUpload(e.target.files[0]);
});

async function handleUpload(file) {
    // UI Transition
    dropZone.classList.add('hidden');
    loadingArea.classList.remove('hidden');

    // Simulate Processing
    setTimeout(() => {
        loadingArea.classList.add('hidden');
        resultCard.classList.remove('hidden');
        
        // Mock Data
        document.getElementById('pName').innerText = "Detected: John Doe";
        document.getElementById('fileHash').innerText = "0x7f...a92b (Immutable)";
    }, 2500);
}
