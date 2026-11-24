let mediaRecorder = null;
let isRecording = false;
let recordStartTime = 0;
let recordTimerInterval = null;
let activeRecordingId = null;
let activeRecordingName = '';
let nextRecordingChunk = 0;
let recordingUploadQueue = Promise.resolve();
let recordingUploadError = null;
let unsavedRecordingChunks = [];
const pendingFileUploads = new Map();
const RECORDING_UPLOAD_CHUNK_BYTES = 8 * 1024 * 1024;

async function createSavedRecording(name, mimeType) {
  const res = await fetch('/api/recordings/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, mime_type: mimeType })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Could not save recording (HTTP ${res.status})`);
  return data.recording_id;
}

async function uploadRecordingChunk(recordingId, index, chunk) {
  const res = await fetch(`/api/recordings/${recordingId}/chunks/${index}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/octet-stream' },
    body: chunk
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data && data.error ? data.error : `Could not save audio chunk ${index + 1}`);
  }
}

async function queueRecordingChunk(recordingId, chunk) {
  const index = nextRecordingChunk++;
  recordingUploadQueue = recordingUploadQueue.then(async () => {
    if (recordingUploadError) {
      unsavedRecordingChunks.push({ index, chunk });
      return;
    }
    let lastError;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        await uploadRecordingChunk(recordingId, index, chunk);
        return;
      } catch (error) {
        lastError = error;
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
    if (lastError) {
      recordingUploadError = lastError;
      unsavedRecordingChunks.push({ index, chunk });
    }
  }).catch(error => {
    recordingUploadError = error;
  });
}

async function finalizeSavedRecording(recordingId, expectedChunks = null) {
  const res = await fetch(`/api/recordings/${recordingId}/finalize`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ expected_chunks: expectedChunks })
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || `Could not finalize recording (HTTP ${res.status})`);
}

async function saveFileAsRecording(file, recordingId) {
  let index = 0;
  for (let start = 0; start < file.size; start += RECORDING_UPLOAD_CHUNK_BYTES) {
    const chunk = file.slice(start, Math.min(start + RECORDING_UPLOAD_CHUNK_BYTES, file.size));
    let lastError;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        await uploadRecordingChunk(recordingId, index, chunk);
        lastError = null;
        break;
      } catch (error) {
        lastError = error;
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
    if (lastError) throw lastError;
    index++;
  }
  await finalizeSavedRecording(recordingId, index);
  return recordingId;
}

async function retryUnsentRecordingChunks(recordingId) {
  for (const item of unsavedRecordingChunks) {
    let saved = false;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        await uploadRecordingChunk(recordingId, item.index, item.chunk);
        saved = true;
        break;
      } catch (error) {
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
      }
    }
    if (!saved) throw new Error(`Could not save audio chunk ${item.index + 1}; keep this page open and retry.`);
  }
  unsavedRecordingChunks = [];
  recordingUploadError = null;
}

function showRetryRecordingUpload() {
  const promptBar = document.querySelector('.prompt-bar');
  if (!promptBar || document.getElementById('retryRecordingUploadBtn')) return;
  const button = document.createElement('button');
  button.id = 'retryRecordingUploadBtn';
  button.className = 'btn-action';
  button.innerText = 'Retry Saving Recording';
  button.onclick = resumeFailedRecordingUpload;
  promptBar.appendChild(button);
}

async function resumeFailedRecordingUpload() {
  const button = document.getElementById('retryRecordingUploadBtn');
  if (button) button.disabled = true;
  try {
    await recordingUploadQueue;
    if (recordingUploadError) await retryUnsentRecordingChunks(activeRecordingId);
    await finalizeSavedRecording(activeRecordingId, nextRecordingChunk);
    if (button) button.remove();
    uploadAndTranscribe(null, activeRecordingId, activeRecordingName);
  } catch (error) {
    alert(`Recording upload is still incomplete: ${error.message}`);
    if (button) button.disabled = false;
  }
}

function clearResults() {
  const container = document.getElementById('cardsContainer');
  container.innerHTML = `
    <div class="hero-box" id="heroBox">
      <div class="hero-title">High-Accuracy Voice Transcription & Intelligence</div>
      <div class="hero-desc">
        Powered by Whisper Medium (769M Pro Studio) and Local Brain LLM Reasoning. Resolves colloquial phonetics, dialogue turns, and code-switching with superior grammatical accuracy.
      </div>
    </div>
  `;
}

async function toggleRecording() {
  const btn = document.getElementById('recordBtn');
  const input = document.getElementById('statusInput');

  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Microphone recording is not supported in this browser context. Please access the application at http://127.0.0.1:7860 or http://localhost:7860, and ensure browser microphone permissions are enabled.");
    return;
  }

  if (!isRecording) {
    let stream = null;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const stamp = new Date().toISOString().replace(/[:.]/g, '-');
      const recordingName = `live_recording_${stamp}.webm`;
      activeRecordingId = await createSavedRecording(recordingName, 'audio/webm');
      activeRecordingName = recordingName;
      nextRecordingChunk = 0;
      recordingUploadError = null;
          unsavedRecordingChunks = [];
      recordingUploadQueue = Promise.resolve();
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = e => {
        if (e.data.size > 0) queueRecordingChunk(activeRecordingId, e.data);
      };

      mediaRecorder.onstop = async () => {
        try {
          await recordingUploadQueue;
          if (recordingUploadError) await retryUnsentRecordingChunks(activeRecordingId);
          await finalizeSavedRecording(activeRecordingId, nextRecordingChunk);
          uploadAndTranscribe(null, activeRecordingId, recordingName);
        } catch (error) {
          alert(`Uploaded chunks are saved on this computer. Some audio may still be unsent; keep this page open and reconnect before trying again.\n\n${error.message}`);
          showRetryRecordingUpload();
          loadSavedRecordings();
        }
      };

      mediaRecorder.start(60000);
      isRecording = true;
      btn.classList.add('recording');
      recordStartTime = Date.now();
      input.value = "Recording... [00:00] (Click red mic to stop & transcribe)";
      recordTimerInterval = setInterval(() => {
        const sec = Math.floor((Date.now() - recordStartTime) / 1000);
        const m = Math.floor(sec / 60);
        const s = sec % 60;
        input.value = `Recording... [${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}] (Click red mic to stop)`;
      }, 1000);

    } catch (err) {
      if (stream) stream.getTracks().forEach(track => track.stop());
      alert("Microphone permission denied or device error: " + err.message + "\\nPlease allow microphone access in your browser address bar.");
    }
  } else {
    isRecording = false;
    clearInterval(recordTimerInterval);
    btn.classList.remove('recording');
    document.getElementById('statusInput').value = "Finalizing live recording...";
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
      mediaRecorder.stream.getTracks().forEach(t => t.stop());
    }
  }
}

function handleFileSelected(input) {
  if (input.files && input.files[0]) {
    uploadAndTranscribe(input.files[0]);
    input.value = '';
  }
}

async function uploadAndTranscribe(file, savedRecordingId = null, savedRecordingName = '') {
  if (!file && !savedRecordingId) return;
  const displayName = file ? file.name : savedRecordingName;
  const modelSize = document.getElementById('modelSelect').value;
  if (modelSize === 'cloud_gemini' || modelSize === 'cloud_groq') {
    const providerName = modelSize === 'cloud_gemini' ? 'Google Gemini' : 'Groq';
    if (!confirm(`This sends the audio to ${providerName} for cloud transcription. The audio may contain confidential information.\n\nContinue?`)) return;
  }
  const statusInput = document.getElementById('statusInput');
  if (statusInput) statusInput.value = "Saving & Transcribing: " + displayName + "...";

  const hero = document.getElementById('heroBox');
  if (hero) hero.style.display = 'none';

  const cardId = 'card_' + Date.now();
  const cardHtml = `
    <div class="result-card" id="${cardId}">
      <div class="result-header">
        <div>
          <b style="font-size:15px; color:#FFFFFF;">${escapeHtml(displayName)}</b>
          <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
            Processing with VerbaCore Engine (Whisper Medium & Brain LLM Reasoning)...
          </div>
        </div>
        <div class="spinner"></div>
      </div>
    </div>
  `;
  document.getElementById('cardsContainer').insertAdjacentHTML('beforeend', cardHtml);
  document.getElementById('chatContainer').scrollTop = document.getElementById('chatContainer').scrollHeight;

  const langMode = document.getElementById('langSelect').value;
  const formData = new FormData();
  formData.append('model', modelSize);
  formData.append('language_mode', langMode);
  let recordingId = savedRecordingId;

  try {
    if (!recordingId) {
      recordingId = await createSavedRecording(file.name, file.type || 'application/octet-stream');
      await saveFileAsRecording(file, recordingId);
    }
    formData.append('recording_id', recordingId);
    const res = await fetch('/api/transcribe', {
      method: 'POST',
      body: formData
    });
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      throw new Error(data && data.error ? data.error : `Upload failed (HTTP ${res.status})`);
    }
    if (!data) {
      throw new Error('The server returned an invalid response.');
    }
    if (data.status === 'success') {
      renderSuccessCard(cardId, displayName, data);
      addHistoryItem(displayName, data.duration_formatted, cardId);
      loadSavedRecordings();
    } else {
      renderErrorCard(cardId, displayName, data.error || 'Transcription failed', data.recording_id || recordingId);
    }
  } catch (err) {
    if (file && recordingId) pendingFileUploads.set(recordingId, file);
    renderErrorCard(cardId, displayName, err.message, recordingId);
  } finally {
    if (statusInput) statusInput.value = "";
  }
}

function addHistoryItem(filename, duration, cardId) {
  const list = document.getElementById('historyList');
  if (list.querySelector('.history-item') === null) {
    list.innerHTML = '';
  }
  const item = document.createElement('div');
  item.className = 'history-item';
  item.innerHTML = `
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
      <polyline points="14 2 14 8 20 8"></polyline>
    </svg>
    <span style="flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(filename)}</span>
    <span style="font-size:11px; color:var(--text-dim);">${duration}</span>
  `;
  item.onclick = () => {
    const target = document.getElementById(cardId);
    if (target) target.scrollIntoView({ behavior: 'smooth' });
  };
  list.prepend(item);
}

function switchViewTab(cardId, tabName) {
  const card = document.getElementById(cardId);
  const vBox = card.querySelector('.view-verbatim');
  const cBox = card.querySelector('.view-clean');
  const btns = card.querySelectorAll('.tab-btn');

  btns.forEach(b => b.classList.remove('active'));

  if (tabName === 'verbatim') {
    vBox.style.display = 'block';
    cBox.style.display = 'none';
    btns[0].classList.add('active');
  } else {
    vBox.style.display = 'none';
    cBox.style.display = 'block';
    btns[1].classList.add('active');
  }
}

function renderSuccessCard(cardId, filename, data) {
  const card = document.getElementById(cardId);
  
  // Verbatim list
  const verbatimHtml = data.segments.map(seg => `
    <div class="segment-row">
      <div class="segment-time">[${formatTime(seg.start)} &rarr; ${formatTime(seg.end)}]</div>
      <div class="segment-speaker">${escapeHtml(seg.speaker)} (${escapeHtml((seg.lang || 'en').toUpperCase())}):</div>
      <div class="segment-text">${escapeHtml(seg.text)}</div>
    </div>
  `).join('');

  // Decluttered list
  const cleanHtml = data.segments.map(seg => `
    <div class="segment-row">
      <div class="segment-speaker">${escapeHtml(seg.speaker)}:</div>
      <div class="segment-text">${escapeHtml(seg.cleaned_text || seg.text)}</div>
    </div>
  `).join('');

  const spkBadgeText = data.brain.is_multi_speaker ? 
    `${data.brain.speaker_count} PARTICIPANTS (CONVERSATION)` : 
    'SINGLE SPEAKER';

  const langBadgeText = Array.isArray(data.brain.languages) && data.brain.languages.length > 0 ? 
    data.brain.languages.join(' + ').toUpperCase() : 
    (data.languages ? data.languages.join(' + ').toUpperCase() : 'MULTILINGUAL');

  const files = data.files || {};
  const pdfTranscript = data.pdf_transcript || files.pdf_transcript;
  const pdfExecutive = data.pdf_executive || files.pdf_executive;
  const docxExecutive = data.docx_executive || files.docx_executive;
  const docxTranscript = data.docx_transcript || files.docx_transcript;
  const txtTranscript = data.txt_transcript || files.txt_transcript;
  const txtExecutive = data.txt_executive || files.txt_executive;

  const reportLinks = [
    [pdfTranscript, 'Transcript PDF', 'Verbatim Timestamped PDF', 'btn-action btn-primary'],
    [pdfExecutive, 'Executive Report PDF', 'Executive Summary Report PDF', 'btn-action btn-purple'],
    [docxExecutive, 'Word Doc (.docx)', 'Executive Report in Word DOCX', 'btn-action'],
    [docxTranscript, 'Verbatim DOCX', 'Verbatim Word Document', 'btn-action'],
    [txtTranscript, 'TXT', 'Plain Text Transcript', 'btn-action'],
    [txtExecutive, 'Executive TXT', 'Executive Plain Text', 'btn-action']
  ].filter(([report]) => report).map(([report, label, title, className]) => `
    <a href="/api/reports/${encodeURIComponent(report)}" download class="${className}" title="${title}">${label}</a>
  `).join('');
  const unavailableExports = data.unavailable_exports && data.unavailable_exports.length
    ? `<span style="font-size:11px; color:var(--text-muted);">Unavailable: ${escapeHtml(data.unavailable_exports.join(', '))} (install the optional export package)</span>`
    : '';
  const recordingActions = data.recording_id ? `
    <a href="/api/recordings/${encodeURIComponent(data.recording_id)}/mp3" class="btn-action btn-primary" title="Convert and download the saved recording as MP3">Download Recording (.mp3)</a>
    <button class="btn-action" onclick="retrySavedRecording('${data.recording_id}', decodeURIComponent('${encodeJsString(filename)}'), 'gemini', '${cardId}')">Retry with Gemini</button>
    <button class="btn-action" onclick="retrySavedRecording('${data.recording_id}', decodeURIComponent('${encodeJsString(filename)}'), 'groq', '${cardId}')">Retry with Groq</button>
  ` : '';

  const engineName = data.engine_used || data.engine || 'VerbaCore Local Engine';
  const isCloud = data.processing_location === 'cloud' || data.fallback_used || engineName.toLowerCase().includes('cloud');

  card.innerHTML = `
    <div class="result-header">
      <div>
        <b style="font-size:15px; color:#FFFFFF;">${escapeHtml(filename)}</b>
        <div style="font-size:12px; color:var(--text-muted); margin-top:4px;">
          Engine: ${escapeHtml(engineName)} &bull; Duration: ${data.duration_formatted} &bull; Words: ${data.word_count} &bull; Ref: ${data.report_id.substring(0,8)}
        </div>
      </div>
      <div class="badge-group">
        ${isCloud ? `<div class="badge-fallback">${escapeHtml(engineName)}</div>` : `<div class="badge-offline" style="font-size:10px; padding:3px 8px;">LOCAL PROCESSING</div>`}
        <div class="lang-badge">${escapeHtml(langBadgeText)}</div>
        <div class="speaker-badge">${escapeHtml(spkBadgeText)}</div>
      </div>
    </div>

    <!-- Executive Summary Box -->
    <div class="exec-summary-box">
      <div class="exec-title">Executive Summary</div>
      <div class="exec-body">${escapeHtml(data.brain.executive_summary)}</div>
    </div>

    <!-- Tab navigation -->
    <div class="tab-nav">
      <button class="tab-btn active" onclick="switchViewTab('${cardId}', 'verbatim')">Verbatim Transcript (Timestamps)</button>
      <button class="tab-btn" onclick="switchViewTab('${cardId}', 'clean')">Conversation Dialogue</button>
    </div>

    <div class="transcript-body view-verbatim">
      ${verbatimHtml || '<i>(No speech detected)</i>'}
    </div>

    <div class="transcript-body view-clean" style="display:none;">
      ${cleanHtml || '<i>(No speech detected)</i>'}
    </div>

    <div class="action-bar">
      ${recordingActions}
      ${reportLinks}
      ${unavailableExports}
      <button class="btn-action" onclick="copyTranscript('${cardId}')">
        Copy Text
      </button>
    </div>
  `;
}

function renderErrorCard(cardId, filename, error, recordingId = null) {
  const card = document.getElementById(cardId);
  const retryFileButton = recordingId && pendingFileUploads.has(recordingId)
    ? `<button class="btn-action" onclick="retryFileUpload('${recordingId}', decodeURIComponent('${encodeJsString(filename)}'), '${cardId}')">Retry saving original file</button>`
    : '';
  const finalizedActions = recordingId && !pendingFileUploads.has(recordingId) ? `
    <a href="/api/recordings/${encodeURIComponent(recordingId)}/mp3" class="btn-action">Download Recording (.mp3)</a>
    <button class="btn-action" onclick="retrySavedRecording('${recordingId}', decodeURIComponent('${encodeJsString(filename)}'), 'gemini', '${cardId}')">Retry with Gemini</button>
    <button class="btn-action" onclick="retrySavedRecording('${recordingId}', decodeURIComponent('${encodeJsString(filename)}'), 'groq', '${cardId}')">Retry with Groq</button>
  ` : '';
  card.innerHTML = `
    <div class="result-header">
      <b style="color:#EF4444;">${escapeHtml(filename)} &bull; Failed</b>
      <span style="font-size:12px; color:#F87171;">Error</span>
    </div>
    <div style="font-size:13px; color:#CBD5E1;">${escapeHtml(error)}</div>
    ${recordingId ? `<div class="action-bar">
      ${retryFileButton}
      ${finalizedActions}
    </div>` : ''}
  `;
}

async function retryFileUpload(recordingId, filename, cardId) {
  const file = pendingFileUploads.get(recordingId);
  if (!file) return;
  const card = document.getElementById(cardId);
  if (card) card.innerHTML = `<div class="result-header"><b>${escapeHtml(filename)} &bull; Saving audio again</b><div class="spinner"></div></div>`;
  try {
    await saveFileAsRecording(file, recordingId);
    pendingFileUploads.delete(recordingId);
    uploadAndTranscribe(null, recordingId, filename);
  } catch (error) {
    renderErrorCard(cardId, filename, error.message, recordingId);
  }
}

async function retrySavedRecording(recordingId, filename, provider, cardId) {
  const providerName = provider === 'gemini' ? 'Google Gemini' : 'Groq';
  if (!confirm(`This sends the saved recording to ${providerName} for cloud transcription. The audio may contain confidential information.\n\nContinue?`)) return;

  const targetCardId = cardId || `card_${Date.now()}`;
  if (!cardId) {
    document.getElementById('cardsContainer').insertAdjacentHTML('beforeend', `
      <div class="result-card" id="${targetCardId}">
        <div class="result-header"><b>${escapeHtml(filename)}</b><div class="spinner"></div></div>
      </div>
    `);
  }
  const card = document.getElementById(targetCardId);
  if (card) {
    card.innerHTML = `<div class="result-header"><b>${escapeHtml(filename)} &bull; Retrying with ${providerName}</b><div class="spinner"></div></div>`;
  }
  const formData = new FormData();
  formData.append('recording_id', recordingId);
  formData.append('model', provider === 'gemini' ? 'cloud_gemini' : 'cloud_groq');
  formData.append('language_mode', document.getElementById('langSelect').value);
  try {
    const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
    const data = await res.json().catch(() => null);
    if (!res.ok || !data) throw new Error(data && data.error ? data.error : `Cloud retry failed (HTTP ${res.status})`);
    if (data.status !== 'success') throw new Error(data.error || 'Cloud retry failed');
    renderSuccessCard(targetCardId, filename, data);
    loadSavedRecordings();
  } catch (error) {
    renderErrorCard(targetCardId, filename, error.message, recordingId);
  }
}

async function recoverSavedRecording(recordingId, filename) {
  if (!confirm('This finalizes the audio chunks that reached this computer. If the browser stopped unexpectedly, the last part of the recording may be missing. Continue with the saved portion?')) return;
  try {
    await finalizeSavedRecording(recordingId);
    await uploadAndTranscribe(null, recordingId, filename);
    loadSavedRecordings();
  } catch (error) {
    alert(`Could not recover the saved recording: ${error.message}`);
  }
}

async function loadSavedRecordings() {
  const list = document.getElementById('historyList');
  if (!list) return;
  try {
    const res = await fetch('/api/recordings');
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `Could not load recordings (HTTP ${res.status})`);
    if (!data.recordings.length) {
      list.innerHTML = '<div style="font-size:12px; color:var(--text-dim); padding:10px 8px;">No saved recordings</div>';
      return;
    }
    list.innerHTML = data.recordings.map(recording => `
      <div class="history-item" style="display:block;">
        <div style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeHtml(recording.display_name)}">${escapeHtml(recording.display_name)}</div>
        <div style="display:flex; gap:5px; flex-wrap:wrap; margin-top:6px;">
          ${recording.finalized
            ? `<a class="btn-action" href="/api/recordings/${encodeURIComponent(recording.recording_id)}/mp3">MP3</a>
               <button class="btn-action" onclick="retrySavedRecording('${recording.recording_id}', decodeURIComponent('${encodeJsString(recording.display_name)}'), 'gemini', '')">Gemini</button>
               <button class="btn-action" onclick="retrySavedRecording('${recording.recording_id}', decodeURIComponent('${encodeJsString(recording.display_name)}'), 'groq', '')">Groq</button>`
            : `<button class="btn-action" onclick="recoverSavedRecording('${recording.recording_id}', decodeURIComponent('${encodeJsString(recording.display_name)}'))">Recover saved chunks</button>`}
        </div>
      </div>
    `).join('');
  } catch (error) {
    console.warn('Could not load saved recordings:', error);
  }
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = (sec % 60).toFixed(2);
  return `${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
}

function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.innerText = text;
  return div.innerHTML;
}

function encodeJsString(text) {
  return encodeURIComponent(String(text)).replace(/'/g, '%27');
}

function copyTranscript(cardId) {
  const card = document.getElementById(cardId);
  const activeTab = card.querySelector('.view-clean').style.display === 'block' ? '.view-clean' : '.view-verbatim';
  const texts = Array.from(card.querySelectorAll(`${activeTab} .segment-text`)).map(el => el.innerText).join(String.fromCharCode(10));
  navigator.clipboard.writeText(texts);
  alert('Transcript copied to clipboard!');
}

// --- Cloud Fallback Settings JS ---
function openCloudModal() {
  fetchCloudConfig();
  document.getElementById('cloudModal').classList.add('open');
}

function closeCloudModal() {
  document.getElementById('cloudModal').classList.remove('open');
}

async function fetchCloudConfig() {
  try {
    const res = await fetch('/api/cloud-config');
    const cfg = await res.json();
    const dot = document.getElementById('cloudDot');
    if (dot) {
      if (cfg.has_gemini || cfg.has_groq) {
        dot.classList.add('active');
      } else {
        dot.classList.remove('active');
      }
    }
    const gemInput = document.getElementById('geminiKeyInput');
    const groqInput = document.getElementById('groqKeyInput');
    const autoCheck = document.getElementById('autoFallbackCheck');
    if (gemInput && cfg.gemini_masked) gemInput.value = cfg.gemini_masked;
    if (groqInput && cfg.groq_masked) groqInput.value = cfg.groq_masked;
    if (autoCheck) autoCheck.checked = cfg.auto_fallback !== false;
  } catch (err) {
    console.warn("Could not fetch cloud config:", err);
  }
}

async function saveCloudConfigSettings() {
  const gemVal = document.getElementById('geminiKeyInput').value.trim();
  const groqVal = document.getElementById('groqKeyInput').value.trim();
  const autoFallback = document.getElementById('autoFallbackCheck').checked;

  const payload = {
    auto_fallback: autoFallback
  };
  if (gemVal && !gemVal.startsWith('***')) payload.gemini_api_key = gemVal;
  if (groqVal && !groqVal.startsWith('***')) payload.groq_api_key = groqVal;

  try {
    const res = await fetch('/api/cloud-config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.status === 'ok') {
      alert('Cloud fallback settings saved successfully!');
      fetchCloudConfig();
      closeCloudModal();
    } else {
      alert('Error saving settings: ' + (data.message || 'Unknown error'));
    }
  } catch (err) {
    alert('Failed to save cloud config: ' + err.message);
  }
}

async function testCloudKey(provider) {
  const inputId = provider === 'gemini' ? 'geminiKeyInput' : 'groqKeyInput';
  const resultId = provider === 'gemini' ? 'geminiTestResult' : 'groqTestResult';
  const val = document.getElementById(inputId).value.trim();
  const resEl = document.getElementById(resultId);

  resEl.className = 'modal-msg';
  resEl.innerText = 'Testing connection...';
  resEl.style.display = 'inline-block';

  try {
    const res = await fetch('/api/test-cloud', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider: provider, key: val })
    });
    const data = await res.json();
    if (data.success) {
      resEl.className = 'modal-msg success';
      resEl.innerText = data.message;
      fetchCloudConfig();
    } else {
      resEl.className = 'modal-msg error';
      resEl.innerText = (data.message || 'Connection failed');
    }
  } catch (err) {
    resEl.className = 'modal-msg error';
    resEl.innerText = err.message;
  }
}

// Initial fetch on page load
document.addEventListener('DOMContentLoaded', () => {
  fetchCloudConfig();
  loadSavedRecordings();
});
setTimeout(fetchCloudConfig, 500);

// Global drag and drop audio files support
window.addEventListener('dragover', (e) => {
  e.preventDefault();
});
window.addEventListener('drop', (e) => {
  e.preventDefault();
  if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
    uploadAndTranscribe(e.dataTransfer.files[0]);
  }
});
