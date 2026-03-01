// MediVault Frontend - Complete Application State & Logic
// Phase 5: Complete redesign with new workflow

// Global state
const state = {
    currentStep: 'upload',
    uploadedFile: null,
    rawText: '',
    ocrConfidence: 0,
    extractedEntities: null,
    prescriptionId: null,
    interactionResults: null,
    audioBlob: null,
    isSaving: false,
};

// DOM Elements Cache
const elements = {
    // Sidebar
    sidebarItems: document.querySelectorAll('.sidebar-item'),
    
    // Progress
    progressSteps: document.querySelectorAll('.progress-step'),
    
    // Step panels
    stepPanels: document.querySelectorAll('.step-panel'),
    successScreen: document.getElementById('success-screen'),
    
    // Step 1: Upload
    uploadZone: document.getElementById('upload-zone'),
    fileInput: document.getElementById('file-input'),
    btnExtractText: document.getElementById('btn-extract-text'),
    btnContinueExtract: document.getElementById('btn-continue-extract'),
    fileConfirmation: document.getElementById('file-confirmation'),
    confirmationFilename: document.getElementById('confirmation-filename'),
    confirmationDetails: document.getElementById('confirmation-details'),
    extractLoading: document.getElementById('extract-loading'),
    uploadPreview: document.getElementById('upload-preview'),
    confidenceScore: document.getElementById('confidence-score'),
    textPreview: document.getElementById('text-preview'),
    errorUpload: document.getElementById('error-upload'),
    
    // Step 2: Extract
    reviewedText: document.getElementById('reviewed-text'),
    btnNormalizeExtract: document.getElementById('btn-normalize-extract'),
    normalizeLoading: document.getElementById('normalize-loading'),
    saveStatus: document.getElementById('save-status'),
    extractPreview: document.getElementById('extract-preview'),
    normalizedText: document.getElementById('normalized-text'),
    entitiesMedications: document.getElementById('entities-medications'),
    entitiesConditions: document.getElementById('entities-conditions'),
    entitiesAllergies: document.getElementById('entities-allergies'),
    btnAdvanceInteract: document.getElementById('btn-advance-interact'),
    errorExtract: document.getElementById('error-extract'),
    
    // Step 3: Interact
    btnCheckInteractions: document.getElementById('btn-check-interactions'),
    interactLoading: document.getElementById('interact-loading'),
    interactPreview: document.getElementById('interact-preview'),
    interactionsList: document.getElementById('interactions-list'),
    btnAdvanceVoice: document.getElementById('btn-advance-voice'),
    errorInteract: document.getElementById('error-interact'),
    
    // Step 4: Voice
    voiceSelect: document.getElementById('voice-select'),
    btnGenerateAudio: document.getElementById('btn-generate-audio'),
    btnSkipVoice: document.getElementById('btn-skip-voice'),
    ttsLoading: document.getElementById('tts-loading'),
    voicePreview: document.getElementById('voice-preview'),
    summaryText: document.getElementById('summary-text'),
    audioPlayer: document.getElementById('audio-player'),
    errorVoice: document.getElementById('error-voice'),
    
    // Success screen
    successRxId: document.getElementById('success-rx-id'),
    successMedications: document.getElementById('success-medications'),
    btnStartOver: document.getElementById('btn-start-over'),
    btnClose: document.getElementById('btn-close'),
    
    // Lab Reports
    labUploadZone: document.getElementById('lab-upload-zone'),
    labFileInput: document.getElementById('lab-file-input'),
    labFileName: document.getElementById('lab-file-name'),
    labTestDate: document.getElementById('lab-test-date'),
    labReportType: document.getElementById('lab-report-type'),
    labName: document.getElementById('lab-name'),
    btnSaveLabReport: document.getElementById('btn-save-lab-report'),
    labError: document.getElementById('lab-error'),
    labLoading: document.getElementById('lab-loading'),
    labSuccess: document.getElementById('lab-success'),
    labSuccessMsg: document.getElementById('lab-success-msg'),
    progressBar: document.querySelector('.progress-bar'),
    
    // Toast
    toastContainer: document.querySelector('.toast-container'),
};

// ===== Toast Notification System =====
function showToast(message, type = 'success') {
    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
    };
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-icon">${icons[type]}</div>
        <div class="toast-text">${message}</div>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Remove after 4 seconds
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ===== UI Helper Functions =====
function setCurrentStep(stepName) {
    state.currentStep = stepName;
    
    // Update sidebar
    elements.sidebarItems.forEach(item => {
        if (item.dataset.step === stepName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // Hide progress bar for lab-reports (non-prescription workflow)
    if (stepName === 'lab-reports') {
        if (elements.progressBar) {
            elements.progressBar.classList.add('hidden');
        }
    } else {
        if (elements.progressBar) {
            elements.progressBar.classList.remove('hidden');
        }
        // Update progress bar for prescription workflow
        const stepIndex = ['upload', 'extract', 'interact', 'voice'].indexOf(stepName);
        elements.progressSteps.forEach((step, index) => {
            if (index < stepIndex) {
                step.classList.add('completed');
                step.classList.remove('active');
            } else if (index === stepIndex) {
                step.classList.add('active');
                step.classList.remove('completed');
            } else {
                step.classList.remove('active', 'completed');
            }
        });
    }
    
    // Update panels
    elements.stepPanels.forEach(panel => {
        panel.classList.toggle('active', panel.id === `step-${stepName}`);
    });
    
    elements.successScreen.style.display = 'none';
}

function showError(element, message) {
    element.textContent = message;
    element.style.display = 'block';
}

function hideError(element) {
    element.style.display = 'none';
}

function renderEntityItems(container, items) {
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="entity-item" style="opacity: 0.6;">—</div>';
        return;
    }
    
    container.innerHTML = items.map(item => {
        const name = typeof item === 'object' ? item.name : item;
        return `<div class="entity-item">${name}</div>`;
    }).join('');
}

function renderMedicationCards(medications) {
    if (!medications || medications.length === 0) {
        return '<div style="grid-column: 1/-1; text-align: center; color: #cbd5e1;">No medications found</div>';
    }
    
    return medications.map(med => `
        <div class="medication-card">
            <div class="medication-name">${med.name || med}</div>
            ${med.dosage ? `<div class="medication-detail">💊 <strong>${med.dosage}</strong></div>` : ''}
            ${med.frequency ? `<div class="medication-detail">🕐 <strong>${med.frequency}</strong></div>` : ''}
            ${med.duration ? `<div class="medication-detail">📅 <strong>${med.duration}</strong></div>` : ''}
        </div>
    `).join('');
}

// ===== API Calls =====
async function apiCall(endpoint, method = 'POST', data = null) {
    try {
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            },
        };
        
        if (data) {
            options.body = JSON.stringify(data);
        }
        
        const response = await fetch(endpoint, options);
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || `HTTP ${response.status}`);
        }
        
        return result;
    } catch (error) {
        console.error(`API call failed: ${endpoint}`, error);
        throw error;
    }
}

async function uploadFile(file) {
    try {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await fetch('/ai/process-document', {
            method: 'POST',
            body: formData,
        });
        
        const result = await response.json();
        
        if (!response.ok) {
            throw new Error(result.error || 'Upload failed');
        }
        
        return result;
    } catch (error) {
        console.error('Upload failed:', error);
        throw error;
    }
}

// ===== STEP 1: UPLOAD =====
function initUploadStep() {
    // Drag and drop
    elements.uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadZone.style.borderColor = '#fb923c';
        elements.uploadZone.style.background = 'rgba(251, 146, 60, 0.08)';
    });
    
    elements.uploadZone.addEventListener('dragleave', () => {
        elements.uploadZone.style.borderColor = 'rgba(251, 146, 60, 0.3)';
        elements.uploadZone.style.background = 'rgba(255, 255, 255, 0.04)';
    });
    
    elements.uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.uploadZone.style.borderColor = 'rgba(251, 146, 60, 0.3)';
        elements.uploadZone.style.background = 'rgba(255, 255, 255, 0.04)';
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            handleFileSelect(files[0]);
        }
    });
    
    // Click to upload
    elements.uploadZone.addEventListener('click', () => {
        elements.fileInput.click();
    });
    
    elements.fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileSelect(e.target.files[0]);
        }
    });
    
    // Extract button
    elements.btnExtractText.addEventListener('click', handleExtractText);
    
    // Continue to Normalize button
    elements.btnContinueExtract.addEventListener('click', () => {
        setCurrentStep('extract');
        elements.reviewedText.value = state.rawText;
        elements.reviewedText.focus();
    });
}

function handleFileSelect(file) {
    state.uploadedFile = file;
    
    // Show confirmation card (CHANGE 1: File confirmation card)
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    elements.confirmationFilename.textContent = `✓ ${file.name}`;
    elements.confirmationDetails.textContent = `${fileSize} MB • Ready to extract`;
    elements.fileConfirmation.style.display = 'block';
    
    // Enable extract button
    elements.btnExtractText.disabled = false;
    elements.btnExtractText.style.cursor = 'pointer';
    
    hideError(elements.errorUpload);
}

async function handleExtractText() {
    if (!state.uploadedFile) return;
    
    elements.btnExtractText.disabled = true;
    elements.extractLoading.style.display = 'block';
    hideError(elements.errorUpload);
    
    try {
        const result = await uploadFile(state.uploadedFile);
        
        state.rawText = result.raw_text;
        state.ocrConfidence = result.confidence || 0;
        
        // Show preview
        elements.textPreview.textContent = state.rawText;
        // Confidence from backend is already 0-100 (from AWS Textract)
        elements.confidenceScore.textContent = `${Math.round(state.ocrConfidence)}%`;
        elements.uploadPreview.style.display = 'block';
        
        showToast('✓ Text extracted successfully', 'success');
        
    } catch (error) {
        showError(elements.errorUpload, `❌ ${error.message}`);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        elements.extractLoading.style.display = 'none';
        elements.btnExtractText.disabled = false;
    }
}

// ===== STEP 2: EXTRACT & NORMALIZE =====
function initExtractStep() {
    elements.btnNormalizeExtract.addEventListener('click', handleNormalizeExtract);
}

async function handleNormalizeExtract() {
    const text = elements.reviewedText.value.trim();
    
    if (!text) {
        showToast('Please enter text to normalize', 'warning');
        return;
    }
    
    elements.btnNormalizeExtract.disabled = true;
    elements.normalizeLoading.style.display = 'block';
    hideError(elements.errorExtract);
    
    try {
        // Call normalize endpoint
        const result = await apiCall('/ai/normalize-and-extract', 'POST', {
            reviewed_text: text,
            patient_verified: true,
            ocr_confidence: state.ocrConfidence,
        });
        
        state.extractedEntities = result.entities;
        
        // Show preview
        elements.normalizedText.textContent = text;
        renderEntityItems(elements.entitiesMedications, result.entities.medications || []);
        renderEntityItems(elements.entitiesConditions, result.entities.conditions || []);
        renderEntityItems(elements.entitiesAllergies, result.entities.allergies || []);
        
        elements.extractPreview.style.display = 'block';
        
        // CHANGE 4: Auto-save to database after extraction
        await autoSavePrescription();
        
        showToast('✓ Entities extracted and saved to vault', 'success');
        
    } catch (error) {
        showError(elements.errorExtract, `❌ ${error.message}`);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        elements.normalizeLoading.style.display = 'none';
        elements.btnNormalizeExtract.disabled = false;
    }
}

async function autoSavePrescription() {
    elements.saveStatus.style.display = 'block';
    
    try {
        const result = await apiCall('/ai/save-prescription', 'POST', {
            patient_id: 1,
            doctor_id: 1,
            s3_image_url: 'local-upload',
            entities: state.extractedEntities,
        });
        
        state.prescriptionId = result.prescription_id || result.id;
        elements.saveStatus.style.display = 'none';
        
        return result;
    } catch (error) {
        elements.saveStatus.style.display = 'none';
        // Show warning but don't block
        showToast('⚠ Save failed — continuing anyway', 'warning');
        console.error('Auto-save failed:', error);
    }
}

// ===== STEP 3: INTERACTIONS (Optional - Manual Check) =====
function initInteractStep() {
    elements.btnCheckInteractions.addEventListener('click', autoCheckInteractions);
    elements.btnAdvanceVoice.addEventListener('click', () => {
        setCurrentStep('voice');
    });
}

async function autoCheckInteractions() {
    if (!state.extractedEntities || !state.extractedEntities.medications) {
        showToast('No medications to check', 'warning');
        return;
    }
    
    try {
        elements.btnCheckInteractions.disabled = true;
        elements.interactLoading.style.display = 'block';
        hideError(elements.errorInteract);
        
        // Check all medication pairs for interactions
        const meds = state.extractedEntities.medications || [];
        if (meds.length < 2) {
            showToast('✓ Only 1 medication - no interactions possible', 'success');
            elements.interactLoading.style.display = 'none';
            elements.btnCheckInteractions.disabled = false;
            return;
        }
        
        // Check each pairing
        let allInteractions = [];
        for (let i = 0; i < meds.length; i++) {
            for (let j = i + 1; j < meds.length; j++) {
                const med1 = typeof meds[i] === 'object' ? meds[i].name : meds[i];
                const med2 = typeof meds[j] === 'object' ? meds[j].name : meds[j];
                const result = await apiCall('/ai/check-interaction', 'POST', {
                    new_med: med1,
                    current_meds: [med2],
                });
                if (result.interactions) {
                    // Filter out "unknown" interactions and add drug pair info
                    result.interactions.forEach(interaction => {
                        if (interaction.severity && interaction.severity.toLowerCase() !== 'unknown') {
                            interaction._drug1 = med1;
                            interaction._drug2 = med2;
                            allInteractions.push(interaction);
                        }
                    });
                }
            }
        }
        
        state.interactionResults = { interactions: allInteractions };
        
        elements.interactLoading.style.display = 'none';
        
        // Only show if there are actual interactions
        if (allInteractions.length > 0) {
            elements.interactPreview.style.display = 'block';
            elements.interactionsList.innerHTML = allInteractions.map(interaction => `
                <div class="interaction-item">
                    <div style="margin-bottom: 8px;">
                        <span class="severity-badge severity-${interaction.severity ? interaction.severity.toLowerCase() : 'high'}">${interaction.severity || 'HIGH'}</span>
                        <strong>${interaction._drug1} + ${interaction._drug2}</strong>
                    </div>
                    <div style="color: #cbd5e1; font-size: 13px;">${interaction.summary || interaction.mechanism || 'Interaction detected'}</div>
                </div>
            `).join('');
            showToast(`⚠️ ${allInteractions.length} interaction(s) found!`, 'warning');
        } else {
            showToast('✓ No interactions found', 'success');
        }
        
    } catch (error) {
        elements.interactLoading.style.display = 'none';
        showError(elements.errorInteract, `❌ ${error.message}`);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        elements.btnCheckInteractions.disabled = false;
    }
}

// ===== STEP 4: VOICE (Optional with Skip button) =====
function initVoiceStep() {
    elements.btnGenerateAudio.addEventListener('click', handleGenerateAudio);
    elements.btnSkipVoice.addEventListener('click', showSuccessScreen); // CHANGE 3: Skip button
}

async function handleGenerateAudio() {
    const voice = elements.voiceSelect.value;
    
    if (!state.extractedEntities) {
        showToast('No entities to generate audio for', 'warning');
        return;
    }
    
    elements.btnGenerateAudio.disabled = true;
    elements.ttsLoading.style.display = 'block';
    hideError(elements.errorVoice);
    
    try {
        // Create summary text
        const summaryContent = createSummaryText();
        elements.summaryText.textContent = summaryContent;
        
        // Call TTS endpoint
        const result = await apiCall('/ai/tts', 'POST', {
            text: summaryContent,
            voice_id: voice,
        });
        
        if (result.audio_url || result.audio) {
            const audioData = result.audio_url ? result.audio : result.audio;
            
            // Create blob and play
            if (typeof audioData === 'string' && audioData.startsWith('data:')) {
                const arr = audioData.split(',');
                const bstr = atob(arr[1]);
                const n = bstr.length;
                const u8arr = new Uint8Array(n);
                for (let i = 0; i < n; i++) {
                    u8arr[i] = bstr.charCodeAt(i);
                }
                const blob = new Blob([u8arr], { type: 'audio/mpeg' });
                const audioUrl = URL.createObjectURL(blob);
                elements.audioPlayer.src = audioUrl;
                elements.audioPlayer.style.display = 'block';
                state.audioBlob = blob;
            }
        }
        
        elements.voicePreview.style.display = 'block';
        showToast('✓ Audio generated successfully', 'success');
        
    } catch (error) {
        showError(elements.errorVoice, `❌ ${error.message}`);
        showToast(`Error: ${error.message}`, 'error');
    } finally {
        elements.ttsLoading.style.display = 'none';
        elements.btnGenerateAudio.disabled = false;
    }
}

function createSummaryText() {
    const entities = state.extractedEntities;
    let summary = 'Patient Prescription Summary. ';
    
    if (entities.medications && entities.medications.length > 0) {
        summary += `Medications: ${entities.medications.map(m => typeof m === 'string' ? m : m.name).join(', ')}. `;
    }
    
    if (entities.conditions && entities.conditions.length > 0) {
        summary += `Conditions: ${entities.conditions.join(', ')}. `;
    }
    
    if (entities.allergies && entities.allergies.length > 0) {
        summary += `Allergies: ${entities.allergies.join(', ')}. `;
    }
    
    return summary;
}

// ===== SUCCESS SCREEN =====
function showSuccessScreen() {
    elements.stepPanels.forEach(panel => panel.classList.remove('active'));
    
    // Populate success details
    elements.successRxId.textContent = state.prescriptionId || '—';
    
    if (state.extractedEntities && state.extractedEntities.medications) {
        elements.successMedications.innerHTML = renderMedicationCards(state.extractedEntities.medications);
    }
    
    elements.successScreen.style.display = 'block';
    
    // Update progress to completed
    elements.progressSteps.forEach(step => {
        step.classList.add('completed');
        step.classList.remove('active');
    });
    
    showToast('✓ Prescription processing complete', 'success');
}

// ===== Lab Reports Functions =====
function displayLabFileName(file) {
    elements.labFileName.textContent = `✓ ${file.name} (${(file.size / 1024).toFixed(2)} KB)`;
    elements.labFileName.style.display = 'block';
}

async function handleSaveLabReport() {
    hideError(elements.labError);
    elements.labSuccess.style.display = 'none';
    
    // Validate inputs
    const file = elements.labFileInput.files[0];
    const testDate = elements.labTestDate.value;
    const reportType = elements.labReportType.value;
    const labName = elements.labName.value;
    
    if (!file) {
        showError(elements.labError, 'Please select a file');
        return;
    }
    
    if (!testDate) {
        showError(elements.labError, 'Please select test date');
        return;
    }
    
    if (!reportType) {
        showError(elements.labError, 'Please select report type');
        return;
    }
    
    // Show loading
    elements.labLoading.style.display = 'block';
    elements.btnSaveLabReport.disabled = true;
    
    try {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('patient_id', 1); // TODO: Get actual patient ID
        formData.append('test_date', testDate);
        formData.append('report_type', reportType);
        if (labName) {
            formData.append('lab_name', labName);
        }
        
        console.log('Sending lab report to /ai/save-lab-report...');
        const response = await fetch('/ai/save-lab-report', {
            method: 'POST',
            body: formData
        });
        
        console.log('Response status:', response.status);
        
        let result;
        try {
            result = await response.json();
            console.log('Response body:', result);
        } catch (e) {
            console.error('Failed to parse response JSON:', e);
            const text = await response.text();
            console.log('Response text:', text);
            throw new Error(`Server error (${response.status}): ${text.substring(0, 200)}`);
        }
        
        if (!response.ok || !result.ok) {
            throw new Error(result.error || `Server error (${response.status})`);
        }
        
        // Show success
        elements.labLoading.style.display = 'none';
        elements.labSuccess.style.display = 'block';
        elements.labSuccessMsg.textContent = `Lab report #${result.lab_report_id} saved successfully!`;
        
        // Reset form
        setTimeout(() => {
            elements.labFileInput.value = '';
            elements.labTestDate.value = '';
            elements.labReportType.value = '';
            elements.labName.value = '';
            elements.labFileName.style.display = 'none';
            elements.labSuccess.style.display = 'none';
            elements.btnSaveLabReport.disabled = false;
            showToast('Lab report saved successfully', 'success');
        }, 2000);
        
    } catch (error) {
        console.error('Save lab report failed:', error);
        console.error('Error stack:', error.stack);
        elements.labLoading.style.display = 'none';
        elements.btnSaveLabReport.disabled = false;
        showError(elements.labError, error.message || 'Failed to save lab report');
    }
}

// ===== Initialization =====
function initEventListeners() {
    // Sidebar navigation
    elements.sidebarItems.forEach(item => {
        item.addEventListener('click', () => {
            const step = item.dataset.step;
            // Lab reports can be accessed anytime
            if (step === 'lab-reports') {
                setCurrentStep(step);
                return;
            }
            // Prescription workflow has prerequisites
            if (step === 'extract' && !state.rawText) {
                showToast('Please extract text first', 'warning');
                return;
            }
            if (step === 'interact' && !state.extractedEntities) {
                showToast('Please normalize & extract first', 'warning');
                return;
            }
            if (step === 'voice' && !state.extractedEntities) {
                showToast('Please normalize & extract first', 'warning');
                return;
            }
            setCurrentStep(step);
        });
    });
    
    // Button listeners
    elements.btnAdvanceInteract.addEventListener('click', () => {
        setCurrentStep('interact');
        // CHANGE 2: Auto-check interactions when arriving at step 3
        setTimeout(autoCheckInteractions, 100);
    });
    
    // Start over buttons
    elements.btnStartOver.addEventListener('click', () => {
        // Reset state
        state.currentStep = 'upload';
        state.uploadedFile = null;
        state.rawText = '';
        state.extractedEntities = null;
        state.interactionResults = null;
        state.audioBlob = null;
        
        // Clear form
        elements.fileInput.value = '';
        elements.reviewedText.value = '';
        elements.voiceSelect.value = 'Joanna';
        
        // Hide elements
        elements.fileConfirmation.style.display = 'none';
        elements.uploadPreview.style.display = 'none';
        elements.extractPreview.style.display = 'none';
        elements.interactPreview.style.display = 'none';
        elements.voicePreview.style.display = 'none';
        elements.audioPlayer.style.display = 'none';
        elements.audioPlayer.src = '';
        
        // Reset buttons
        elements.btnExtractText.disabled = true;
        elements.btnGenerateAudio.disabled = false;
        
        setCurrentStep('upload');
    });
    
    elements.btnClose.addEventListener('click', () => {
        elements.btnStartOver.click();
    });

    // Lab Reports handlers
    if (elements.labUploadZone) {
        // Drag and drop
        elements.labUploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            elements.labUploadZone.style.borderColor = '#fb923c';
            elements.labUploadZone.style.background = 'rgba(251, 146, 60, 0.08)';
        });
        
        elements.labUploadZone.addEventListener('dragleave', () => {
            elements.labUploadZone.style.borderColor = 'rgba(251, 146, 60, 0.3)';
            elements.labUploadZone.style.background = 'rgba(255, 255, 255, 0.04)';
        });
        
        elements.labUploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            elements.labUploadZone.style.borderColor = 'rgba(251, 146, 60, 0.3)';
            elements.labUploadZone.style.background = 'rgba(255, 255, 255, 0.04)';
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                elements.labFileInput.files = files;
                displayLabFileName(files[0]);
            }
        });
        
        elements.labUploadZone.addEventListener('click', () => {
            elements.labFileInput.click();
        });
        
        elements.labFileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                displayLabFileName(e.target.files[0]);
            }
        });
        
        // Save button
        elements.btnSaveLabReport.addEventListener('click', handleSaveLabReport);
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initUploadStep();
    initExtractStep();
    initInteractStep();
    initVoiceStep();
    initEventListeners();
    
    // Show initial step
    setCurrentStep('upload');
});
