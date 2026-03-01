/* MediVault HITL - Vanilla JavaScript */

const state = {
    currentStep: 'upload',
    extractedText: '',
    confidence: 0,
    entities: {},
    interactions: [],
    currentMeds: []
};

/* DOM Elements */
const els = {
    // File upload
    fileInput: document.getElementById('file-input'),
    uploadZone: document.getElementById('upload-zone'),
    btnUpload: document.getElementById('btn-upload'),
    
    // Steps
    stepPanels: document.querySelectorAll('.step-panel'),
    stepNavs: document.querySelectorAll('.step-nav'),
    
    // Upload results
    confidenceScore: document.getElementById('confidence-score'),
    reviewStatus: document.getElementById('review-status'),
    textPreview: document.getElementById('text-preview'),
    uploadPreview: document.getElementById('upload-preview'),
    errorUpload: document.getElementById('error-upload'),
    btnAdvanceExtract: document.getElementById('btn-advance-extract'),
    
    // Extract
    reviewedText: document.getElementById('reviewed-text'),
    btnNormalize: document.getElementById('btn-normalize'),
    extractPreview: document.getElementById('extract-preview'),
    normalizedText: document.getElementById('normalized-text'),
    errorExtract: document.getElementById('error-extract'),
    btnAdvanceInteract: document.getElementById('btn-advance-interact'),
    
    // Entities
    entitiesMedications: document.getElementById('entities-medications'),
    entitiesConditions: document.getElementById('entities-conditions'),
    entitiesAllergies: document.getElementById('entities-allergies'),
    entitiesInstructions: document.getElementById('entities-instructions'),
    
    // Interact
    newMedInput: document.getElementById('new-med-input'),
    medAddInput: document.getElementById('med-add-input'),
    medTags: document.getElementById('med-tags'),
    btnCheckInteraction: document.getElementById('btn-check-interaction'),
    interactPreview: document.getElementById('interact-preview'),
    interactionsList: document.getElementById('interactions-list'),
    errorInteract: document.getElementById('error-interact'),
    btnAdvanceVoice: document.getElementById('btn-advance-voice'),
    
    // Voice
    voiceSelect: document.getElementById('voice-select'),
    btnGenerateAudio: document.getElementById('btn-generate-audio'),
    audioPlayer: document.getElementById('audio-player'),
    summaryText: document.getElementById('summary-text'),
    voicePreview: document.getElementById('voice-preview'),
    errorVoice: document.getElementById('error-voice'),
    btnReset: document.getElementById('btn-reset'),
    
    // Debug
    debugTable: document.getElementById('debug-table')
};

/* ===== Event Listeners ===== */

// Upload zone
els.uploadZone.addEventListener('click', () => els.fileInput.click());

els.uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    els.uploadZone.style.borderColor = '#3498db';
    els.uploadZone.style.background = '#e3f2fd';
});

els.uploadZone.addEventListener('dragleave', () => {
    els.uploadZone.style.borderColor = '#bdc3c7';
    els.uploadZone.style.background = '#ecf0f1';
});

els.uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    els.uploadZone.style.borderColor = '#bdc3c7';
    els.uploadZone.style.background = '#ecf0f1';
    
    if (e.dataTransfer.files.length > 0) {
        els.fileInput.files = e.dataTransfer.files;
        handleFileChange();
    }
});

els.fileInput.addEventListener('change', handleFileChange);
els.btnUpload.addEventListener('click', processDocument);
els.btnAdvanceExtract.addEventListener('click', () => showStep('extract'));
els.btnNormalize.addEventListener('click', callNormalizeExtract);
els.btnAdvanceInteract.addEventListener('click', () => showStep('interact'));
els.btnCheckInteraction.addEventListener('click', callCheckInteraction);
els.btnAdvanceVoice.addEventListener('click', () => showStep('voice'));
els.btnGenerateAudio.addEventListener('click', callTts);
els.btnReset.addEventListener('click', resetApp);

els.medAddInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        const med = els.medAddInput.value.trim();
        if (med) {
            state.currentMeds.push(med);
            els.medAddInput.value = '';
            renderMedTags();
        }
    }
});

document.querySelectorAll('.step-nav').forEach(nav => {
    nav.addEventListener('click', () => {
        const step = nav.dataset.step;
        showStep(step);
    });
});

/* ===== File Upload ===== */

function handleFileChange() {
    const file = els.fileInput.files[0];
    if (file) {
        els.btnUpload.disabled = false;
        els.btnUpload.innerHTML = '<span>🔄 Extract Text</span>';
    }
}

async function processDocument() {
    const file = els.fileInput.files[0];
    if (!file) {
        showError('upload', 'Please select a file');
        return;
    }

    clearError('upload');
    els.btnUpload.disabled = true;
    els.btnUpload.innerHTML = '<span>⏳ Processing...</span>';

    try {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch('/ai/process-document', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        logDebug('/ai/process-document', 'POST', response.status, {file: file.name}, data);

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'Failed to process document');
        }

        state.extractedText = data.raw_text;
        state.confidence = data.confidence;

        els.textPreview.textContent = data.raw_text;
        els.confidenceScore.textContent = data.confidence.toFixed(1) + '%';
        els.confidenceScore.style.background = data.confidence > 80 
            ? 'linear-gradient(135deg, #2ecc71, #27ae60)' 
            : '#ffc107';

        els.reviewStatus.textContent = data.requires_review ? 'Yes' : 'No';
        els.reviewStatus.style.background = data.requires_review ? '#fff3cd' : '#d4edda';
        els.reviewStatus.style.color = data.requires_review ? '#856404' : '#155724';

        els.reviewedText.value = data.raw_text;
        els.uploadPreview.style.display = 'block';
        els.btnAdvanceExtract.disabled = false;

    } catch (error) {
        console.error(error);
        showError('upload', error.message);
    } finally {
        els.btnUpload.disabled = false;
        els.btnUpload.innerHTML = '<span>🔄 Extract Text</span>';
    }
}

/* ===== Normalize & Extract ===== */

async function callNormalizeExtract() {
    const text = els.reviewedText.value.trim();
    if (!text) {
        showError('extract', 'Please enter text');
        return;
    }

    clearError('extract');
    els.btnNormalize.disabled = true;
    els.btnNormalize.innerHTML = '<span>⏳ Processing...</span>';

    try {
        const payload = {
            reviewed_text: text,
            patient_verified: true,
            ocr_confidence: state.confidence
        };

        const response = await fetch('/ai/normalize-and-extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        logDebug('/ai/normalize-and-extract', 'POST', response.status, payload, data);

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'Failed to extract entities');
        }

        state.entities = data.entities;
        els.normalizedText.textContent = data.normalized.cleaned_text;

        renderEntities(data.entities);
        els.extractPreview.style.display = 'block';

    } catch (error) {
        console.error(error);
        showError('extract', error.message);
    } finally {
        els.btnNormalize.disabled = false;
        els.btnNormalize.innerHTML = '<span>⚡ Normalize & Extract</span>';
    }
}

/* ===== Check Interaction ===== */

async function callCheckInteraction() {
    const newMed = els.newMedInput.value.trim();
    if (!newMed) {
        showError('interact', 'Please enter a medication');
        return;
    }

    const currentMeds = state.currentMeds.length > 0 
        ? state.currentMeds 
        : (state.entities.medications || []);

    clearError('interact');
    els.btnCheckInteraction.disabled = true;
    els.btnCheckInteraction.innerHTML = '<span>⏳ Checking...</span>';

    try {
        const payload = {
            new_med: newMed,
            current_meds: currentMeds
        };

        const response = await fetch('/ai/check-interaction', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        logDebug('/ai/check-interaction', 'POST', response.status, payload, data);

        if (!response.ok || !data.ok) {
            throw new Error(data.error || 'Failed to check interactions');
        }

        state.interactions = data.interactions || [];
        renderInteractions(data);
        els.interactPreview.style.display = 'block';

    } catch (error) {
        console.error(error);
        showError('interact', error.message);
    } finally {
        els.btnCheckInteraction.disabled = false;
        els.btnCheckInteraction.innerHTML = '<span>🔍 Check Interactions</span>';
    }
}

/* ===== Text-to-Speech ===== */

async function callTts() {
    const summary = generateSummary();
    if (!summary) {
        showError('voice', 'No text to synthesize');
        return;
    }

    clearError('voice');
    els.btnGenerateAudio.disabled = true;
    els.btnGenerateAudio.innerHTML = '<span>⏳ Generating...</span>';

    try {
        const payload = {
            text: summary,
            voice_id: els.voiceSelect.value
        };

        const response = await fetch('/ai/tts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        logDebug('/ai/tts', 'POST', response.status, payload, {audio: 'audio/mpeg'});

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const blob = await response.blob();
        const url = URL.createObjectURL(blob);

        els.audioPlayer.src = url;
        els.summaryText.textContent = summary;
        els.voicePreview.style.display = 'block';

    } catch (error) {
        console.error(error);
        showError('voice', error.message);
    } finally {
        els.btnGenerateAudio.disabled = false;
        els.btnGenerateAudio.innerHTML = '<span>🎤 Generate Audio</span>';
    }
}

/* ===== Rendering ===== */

function renderEntities(entities) {
    // Render medications (objects with name, dosage, frequency, etc.)
    const renderMedicationList = (container, items) => {
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<div style="color: #bdc3c7; font-size: 12px; padding: 8px;">None found</div>';
            return;
        }
        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'entity-item';
            
            // Handle medication object
            if (typeof item === 'object' && item.name) {
                let html = `<strong>${item.name}</strong>`;
                if (item.dosage) html += `<br><small>Dosage: ${item.dosage}</small>`;
                if (item.frequency) html += `<br><small>Frequency: ${item.frequency}</small>`;
                if (item.duration) html += `<br><small>Duration: ${item.duration}</small>`;
                div.innerHTML = html;
            } else {
                // Handle simple strings
                div.textContent = item;
            }
            
            container.appendChild(div);
        });
    };
    
    // Render simple list (strings)
    const render = (container, items) => {
        container.innerHTML = '';
        if (!items || items.length === 0) {
            container.innerHTML = '<div style="color: #bdc3c7; font-size: 12px; padding: 8px;">None found</div>';
            return;
        }
        items.forEach(item => {
            const div = document.createElement('div');
            div.className = 'entity-item';
            div.textContent = typeof item === 'string' ? item : JSON.stringify(item);
            container.appendChild(div);
        });
    };

    // Use special rendering for medications (objects), simple rendering for others (strings)
    renderMedicationList(els.entitiesMedications, entities.medications);
    render(els.entitiesConditions, entities.conditions);
    render(els.entitiesAllergies, entities.allergies);
    render(els.entitiesInstructions, entities.instructions);
}

function renderMedTags() {
    els.medTags.innerHTML = '';
    state.currentMeds.forEach((med, idx) => {
        const tag = document.createElement('div');
        tag.className = 'tag';
        tag.innerHTML = `${med} <button data-idx="${idx}">✕</button>`;
        tag.querySelector('button').addEventListener('click', () => {
            state.currentMeds.splice(idx, 1);
            renderMedTags();
        });
        els.medTags.appendChild(tag);
    });
}

function renderInteractions(data) {
    els.interactionsList.innerHTML = '';

    if (!data.interactions || data.interactions.length === 0) {
        const div = document.createElement('div');
        div.className = 'interaction-item safe';
        div.innerHTML = '<strong>✅ No significant interactions found</strong>';
        els.interactionsList.appendChild(div);
        return;
    }

    data.interactions.forEach(inter => {
        const div = document.createElement('div');
        div.className = 'interaction-item';
        
        const severityClass = inter.severity === 'high' ? 'severity-high' 
            : inter.severity === 'moderate' ? 'severity-moderate' 
            : 'severity-low';

        div.innerHTML = `
            <strong>${inter.medication}</strong>
            <p>${inter.description || 'Interaction detected'}</p>
            <span class="severity-badge ${severityClass}">${(inter.severity || 'Unknown').toUpperCase()}</span>
        `;
        els.interactionsList.appendChild(div);
    });
}

function generateSummary() {
    const e = state.entities || {};
    
    // Handle medications that may be objects with name property
    const medications = (e.medications || []).map(med => {
        return typeof med === 'object' && med.name ? med.name : med;
    }).join(', ') || 'None listed';
    
    const conditions = (e.conditions || []).join(', ') || 'None listed';
    const allergies = (e.allergies || []).join(', ') || 'No known allergies';
    const instructions = (e.instructions || []).join('. ') || 'Standard care';

    return `Patient Medical Summary. Medications: ${medications}. Medical Conditions: ${conditions}. Allergies: ${allergies}. Care Instructions: ${instructions}.`;
}

/* ===== UI Helpers ===== */

function showStep(step) {
    els.stepPanels.forEach(panel => panel.classList.remove('active'));
    els.stepNavs.forEach(nav => nav.classList.remove('active'));

    const panel = document.getElementById(`step-${step}`);
    const nav = document.querySelector(`[data-step="${step}"]`);

    if (panel) panel.classList.add('active');
    if (nav) nav.classList.add('active');

    state.currentStep = step;
}

function showError(type, message) {
    const box = document.getElementById(`error-${type}`);
    if (box) {
        box.textContent = '❌ ' + message;
        box.style.display = 'block';
    }
}

function clearError(type) {
    const box = document.getElementById(`error-${type}`);
    if (box) box.style.display = 'none';
}

function logDebug(endpoint, method, status, payload, response) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td><strong>${endpoint}</strong></td>
        <td>${method}</td>
        <td style="color: ${status >= 200 && status < 300 ? '#2ecc71' : '#e74c3c'};">${status}</td>
        <td style="font-size: 10px; max-width: 200px;">
            <details style="cursor: pointer;">
                <summary>View</summary>
                <pre style="margin-top: 4px; background: #f8f9fa; padding: 4px; font-size: 9px; overflow-x: auto;">
Req: ${JSON.stringify(payload).substring(0, 100)}...
                </pre>
            </details>
        </td>
    `;
    els.debugTable.innerHTML = '';
    els.debugTable.appendChild(row);
}

function resetApp() {
    state.extractedText = '';
    state.confidence = 0;
    state.entities = {};
    state.interactions = [];
    state.currentMeds = [];

    els.fileInput.value = '';
    els.reviewedText.value = '';
    els.newMedInput.value = '';
    els.medAddInput.value = '';
    els.audioPlayer.src = '';

    Object.keys(els).forEach(key => {
        if (key.startsWith('errorUpload') || key.startsWith('error')) {
            const el = els[key];
            if (el) el.style.display = 'none';
        }
    });

    document.querySelectorAll('.preview-box').forEach(box => {
        box.style.display = 'none';
    });

    els.medTags.innerHTML = '';
    showStep('upload');
}

/* Initialize */
console.log('✅ MediVault HITL ready');
showStep('upload');
