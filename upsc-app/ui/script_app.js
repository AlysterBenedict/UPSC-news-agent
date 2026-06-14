/* UPSC News Agent — Dashboard Frontend Controller (Redesigned)
 * KEY FIXES:
 *   - All alert() calls replaced with custom toast notifications
 *   - Icons handled by Lucide (no emojis)
 *   - Proper error handling with user-friendly messages
 */

let timerInterval = null;
let startTime = 0;
let savedPdfPath = '';

// Wait for WebView FFI to be ready
window.addEventListener('pywebviewready', function() {
    initApp();
});

// Fallback in case the event already fired before script load
if (window.pywebview && window.pywebview.api) {
    initApp();
}

function initApp() {
    checkApiKey();
    setDefaultDate();
    setupEventListeners();
    appendSystemLog("System connected to Python backend.");
}

/* ===== TOAST NOTIFICATION SYSTEM (replaces alert()) ===== */
function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    // Icon per type
    const iconMap = {
        error: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
        success: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="9 12 12 15 16 10"/></svg>',
        warn: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
        info: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
    };

    toast.innerHTML = `${iconMap[type] || iconMap.info}<span>${message}</span>`;
    container.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => {
        toast.classList.add('toast-exit');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

/* ===== API KEY CHECK ===== */
function checkApiKey() {
    window.pywebview.api.get_api_key().then(function(response) {
        if (response.success && response.api_key) {
            showSection('dashboardSection');
            updateStatus('connected', 'API Connected');
            
            const key = response.api_key;
            const masked = key.slice(0, 8) + '••••••••••••' + key.slice(-4);
            document.getElementById('maskedKey').innerText = masked;
        } else {
            showSection('apiKeySection');
            updateStatus('disconnected', 'Disconnected');
        }
    }).catch(function(err) {
        appendSystemLog("Error checking API key: " + err, "error");
    });
}

/* ===== DEFAULT DATE ===== */
function setDefaultDate() {
    const today = new Date();
    const yyyy = today.getFullYear();
    let mm = today.getMonth() + 1;
    let dd = today.getDate();
    if (mm < 10) mm = '0' + mm;
    if (dd < 10) dd = '0' + dd;
    document.getElementById('dateInput').value = yyyy + '-' + mm + '-' + dd;
}

/* ===== EVENT LISTENERS ===== */
function setupEventListeners() {
    // Save Key
    document.getElementById('saveKeyBtn').addEventListener('click', function() {
        const keyInput = document.getElementById('apiKeyInput').value.trim();
        if (!keyInput) {
            showToast("Please enter a valid NVIDIA NIM API Key.", "warn");
            return;
        }
        
        appendSystemLog("Saving API Key...");
        window.pywebview.api.save_api_key(keyInput).then(function(response) {
            if (response.success) {
                showToast("API Key successfully configured!", "success");
                appendSystemLog("API Key configured.", "success");
                checkApiKey();
                document.getElementById('apiKeyInput').value = '';
            } else {
                showToast("Error saving API Key: " + response.error, "error");
                appendSystemLog("Error saving API Key: " + response.error, "error");
            }
        });
    });

    // Disconnect Key
    document.getElementById('deleteKeyBtn').addEventListener('click', function() {
        // Use a custom inline confirm via toast rather than native confirm()
        showToast("Disconnecting API key...", "warn", 2000);
        window.pywebview.api.delete_api_key().then(function(response) {
            if (response.success) {
                showToast("API Key disconnected.", "warn");
                appendSystemLog("API Key deleted.", "warn");
                checkApiKey();
            } else {
                showToast("Error deleting key: " + response.error, "error");
            }
        });
    });

    // Execute
    document.getElementById('generateBtn').addEventListener('click', function() {
        const dateVal = document.getElementById('dateInput').value;
        if (!dateVal) {
            showToast("Please select a date.", "warn");
            return;
        }

        window.pywebview.api.select_save_path(dateVal).then(function(response) {
            if (response.success && response.save_path) {
                startExecution(dateVal, response.save_path);
            } else {
                if (response.error && response.error !== "Save path not selected") {
                    showToast("Save dialog error: " + response.error, "error");
                }
                appendSystemLog("Save dialog cancelled or closed.", "warn");
            }
        }).catch(function(err) {
            showToast("Failed to open save dialog: " + err, "error");
            appendSystemLog("Error opening save dialog: " + err, "error");
        });
    });

    // Open PDF
    document.getElementById('openPdfBtn').addEventListener('click', function() {
        if (savedPdfPath) {
            window.pywebview.api.open_file(savedPdfPath);
        }
    });

    // Show in folder
    document.getElementById('openFolderBtn').addEventListener('click', function() {
        if (savedPdfPath) {
            window.pywebview.api.open_folder(savedPdfPath);
        }
    });

    // Return to dashboard
    document.getElementById('backToDashBtn').addEventListener('click', function() {
        showSection('dashboardSection');
        checkApiKey();
    });
}

/* ===== EXECUTION ===== */
function startExecution(dateVal, savePath) {
    showSection('executionSection');
    updateStatus('running', 'Executing Pipeline');
    
    // Reset stepper
    document.querySelectorAll('.stepper .step').forEach(step => {
        step.className = 'step';
    });
    document.getElementById('step_ingest').className = 'step active';
    document.getElementById('currentPhaseName').innerText = 'Starting News Scraper';
    
    // Clear console
    const consoleLog = document.getElementById('consoleLog');
    consoleLog.innerHTML = '<div class="log-line system">[SYSTEM] Starting pipeline execution for ' + dateVal + '...</div>';
    consoleLog.innerHTML += '<div class="log-line system">[SYSTEM] Output destination: ' + savePath + '</div>';

    // Timer
    startTime = Date.now();
    document.getElementById('timeElapsed').innerText = 'Time Elapsed: 0s';
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(updateTimer, 1000);

    // Run pipeline
    window.pywebview.api.run_pipeline(dateVal, savePath);
}

function updateTimer() {
    const elapsed = Math.floor((Date.now() - startTime) / 1000);
    const mins = Math.floor(elapsed / 60);
    const secs = elapsed % 60;
    let timeStr = 'Time Elapsed: ';
    if (mins > 0) timeStr += mins + 'm ' + secs + 's';
    else timeStr += secs + 's';
    document.getElementById('timeElapsed').innerText = timeStr;
}

/* ===== SECTION SWITCHING ===== */
function showSection(sectionId) {
    document.querySelectorAll('.app-content .card').forEach(card => {
        card.classList.remove('active');
    });
    document.getElementById(sectionId).classList.add('active');
    
    const introHeader = document.getElementById('introHeader');
    if (introHeader) {
        if (sectionId === 'executionSection' || sectionId === 'successSection') {
            introHeader.style.display = 'none';
        } else {
            introHeader.style.display = 'block';
        }
    }

    // Re-initialize icons for the newly shown section
    if (window.lucide) {
        setTimeout(() => lucide.createIcons(), 50);
    }
}

function updateStatus(stateClass, labelText) {
    const dot = document.querySelector('.status-dot');
    const label = document.querySelector('.status-text');
    dot.className = 'status-dot ' + stateClass;
    label.innerText = labelText;
}

/* ===== LOG STREAMING ===== */
window.onLog = function(msg) {
    appendSystemLog(msg);
    parseLogForStepping(msg);
};

/* ===== PIPELINE COMPLETION ===== */
window.onPipelineComplete = function(success, messageOrPath) {
    if (timerInterval) clearInterval(timerInterval);
    
    if (success) {
        savedPdfPath = messageOrPath;
        document.getElementById('pdfPathText').innerText = savedPdfPath;
        
        updateStatus('connected', 'API Connected');
        showSection('successSection');
        showToast("Pipeline complete! Digest saved.", "success", 6000);
        appendSystemLog("Pipeline complete! Saved to " + savedPdfPath, "success");
    } else {
        updateStatus('error', 'Execution Failed');
        document.getElementById('currentPhaseName').innerText = 'Execution Failed';
        showToast("Pipeline failed: " + messageOrPath, "error", 8000);
        appendSystemLog("CRITICAL ERROR: " + messageOrPath, "error");
        
        // Add return button
        const consoleLog = document.getElementById('consoleLog');
        const backContainer = document.createElement('div');
        backContainer.style.marginTop = '15px';
        backContainer.innerHTML = '<button onclick="showSection(\'dashboardSection\'); checkApiKey();" class="btn btn-secondary btn-sm">Return to Dashboard</button>';
        consoleLog.appendChild(backContainer);
        consoleLog.scrollTop = consoleLog.scrollHeight;
    }
};

/* ===== STEPPER PHASE DETECTION ===== */
function parseLogForStepping(msg) {
    const text = msg.toLowerCase();
    let logObj = null;
    
    if (msg.trim().startsWith('{') && msg.trim().endsWith('}')) {
        try { logObj = JSON.parse(msg); } catch (e) {}
    }
    
    const eventName = logObj ? logObj.event : '';
    const nodeName = logObj ? logObj.node : '';
    
    // Ingestion
    if (text.includes("auto_running_scraper") || text.includes("starting upsc news scraper") || (logObj && logObj.event === "auto_running_scraper")) {
        setStepActive('step_ingest', 'Crawling News Feeds');
    }
    
    // Normalization
    if ((eventName === "node_complete" && nodeName === "ingest") || 
        (text.includes("node_complete") && (text.includes("node='ingest'") || text.includes('node="ingest"')))) {
        setStepCompleted('step_ingest');
        setStepActive('step_normalize', 'Formatting Article Structures');
    }
    
    // Dedup
    if ((eventName === "node_complete" && nodeName === "normalize") || 
        (text.includes("node_complete") && (text.includes("node='normalize'") || text.includes('node="normalize"')))) {
        setStepCompleted('step_normalize');
        setStepActive('step_dedup', 'Grouping & Deduplicating Articles');
    }
    
    // Analysis
    if ((eventName === "node_complete" && nodeName === "deduplicate") || 
        (text.includes("node_complete") && (text.includes("node='deduplicate'") || text.includes('node="deduplicate"')))) {
        setStepCompleted('step_dedup');
        setStepActive('step_analyze', 'AI Analysis & Fact Verification');
    }
    
    // Writing
    if ((eventName === "node_complete" && (nodeName === "analyze" || nodeName === "verify")) || 
        (text.includes("node_complete") && (text.includes("node='analyze'") || text.includes('node="analyze"') || text.includes("node='verify'") || text.includes('node="verify"')))) {
        setStepCompleted('step_analyze');
        setStepActive('step_write', 'Structuring Syllabus Mapping & Drafts');
    }
    
    // Rendering
    if ((eventName === "node_complete" && (nodeName === "map_upsc" || nodeName === "write_sections" || nodeName === "assemble")) || 
        (text.includes("node_complete") && (
            text.includes("node='map_upsc'") || text.includes('node="map_upsc"') || 
            text.includes("node='write_sections'") || text.includes('node="write_sections"') || 
            text.includes("node='assemble'") || text.includes('node="assemble"')
        ))) {
        setStepCompleted('step_write');
        setStepActive('step_render', 'Rendering A4 Print Document');
    }
    
    // Complete
    if ((eventName === "node_complete" && nodeName === "render") || 
        (text.includes("node_complete") && (text.includes("node='render'") || text.includes('node="render"')))) {
        setStepCompleted('step_render');
        document.getElementById('currentPhaseName').innerText = 'Delivering Reports';
    }
}

function setStepActive(stepId, labelText) {
    document.querySelectorAll('.stepper .step').forEach(step => {
        if (step.id !== stepId && !step.classList.contains('completed')) {
            step.className = 'step';
        }
    });
    const s = document.getElementById(stepId);
    if (s) s.className = 'step active';
    document.getElementById('currentPhaseName').innerText = labelText;
}

function setStepCompleted(stepId) {
    const s = document.getElementById(stepId);
    if (s) s.className = 'step completed';
}

/* ===== CONSOLE LOG RENDERER ===== */
function appendSystemLog(msg, typeOverride = null) {
    const consoleLog = document.getElementById('consoleLog');
    if (!consoleLog) return;

    const lines = msg.split('\n');
    lines.forEach(line => {
        if (!line.trim() && lines.length > 1) return;
        
        let displayLine = line;
        let type = 'info';
        
        // Parse JSON structlog
        if (line.trim().startsWith('{') && line.trim().endsWith('}')) {
            try {
                const ld = JSON.parse(line);
                const ts = ld.timestamp ? ld.timestamp.split('T')[1].substring(0, 8) : '';
                const lvl = ld.level ? ld.level.toUpperCase() : 'INFO';
                const ev = ld.event || '';
                
                let extras = [];
                for (const k in ld) {
                    if (!['timestamp', 'level', 'event'].includes(k)) {
                        extras.push(`${k}=${JSON.stringify(ld[k])}`);
                    }
                }
                const extraStr = extras.length > 0 ? `  (${extras.join(', ')})` : '';
                displayLine = (ts ? `[${ts}] ` : '') + `[${lvl}] ${ev}${extraStr}`;
                
                if (lvl === 'ERROR') type = 'error';
                else if (lvl === 'WARNING' || lvl === 'WARN') type = 'warn';
                else if (ev === 'node_complete') type = 'success';
            } catch (e) {}
        }
        
        if (displayLine === line) {
            if (typeOverride) {
                type = typeOverride;
            } else {
                const lower = line.toLowerCase();
                if (lower.includes('error') || lower.includes('exception') || lower.includes('fail')) type = 'error';
                else if (lower.includes('warn') || lower.includes('retry')) type = 'warn';
                else if (lower.includes('[ok]') || lower.includes('success') || lower.includes('complete')) type = 'success';
                else if (line.startsWith('===') || line.startsWith('  [Auto]') || lower.includes('workflow_start')) type = 'highlight';
                else if (line.startsWith('[SYSTEM]')) type = 'system';
            }
        }

        const div = document.createElement('div');
        div.className = 'log-line ' + type;
        div.textContent = displayLine;
        consoleLog.appendChild(div);
    });

    consoleLog.scrollTop = consoleLog.scrollHeight;
}
