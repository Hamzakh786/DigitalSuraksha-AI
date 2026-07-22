/* Raksha Grid prototype — frontend logic for all 3 features */

// ---------------- Tabs ----------------
document.querySelectorAll(".tab").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach(p => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`panel-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------------- Backend health check ----------------
async function checkHealth() {
  const pill = document.getElementById("apiStatus");
  try {
    const res = await fetch(`${API_BASE_URL}/api/health`);
    if (!res.ok) throw new Error("bad status");
    pill.classList.add("online");
    pill.innerHTML = `<span class="dot"></span> backend connected`;
  } catch (e) {
    pill.classList.add("offline");
    pill.innerHTML = `<span class="dot"></span> backend unreachable — start backend/app.py`;
  }
}
checkHealth();

// ================================================================
// FEATURE 1 — Digital Arrest Scam Detector
// ================================================================
const SAMPLE_TRANSCRIPT = `Unknown number called on WhatsApp video. Man in what looked like a police uniform said he was from "Mumbai Cyber Crime Cell" and that a parcel booked in my name to Taiwan was intercepted with 5 fake passports and drugs. Said an arrest warrant is already issued under my Aadhaar and I must stay on the video call continuously and not tell anyone, or officers would come and arrest me today. Asked me to install AnyDesk to "verify" my bank account and transfer Rs 2,80,000 to a "RBI verification account" to prove the money is not linked to the case, promising a refund in 24 hours after clearance.`;

document.getElementById("scamSampleBtn").addEventListener("click", () => {
  document.getElementById("scamInput").value = SAMPLE_TRANSCRIPT;
});

function riskColor(level) {
  return { low: "var(--risk-low)", medium: "var(--risk-med)", high: "var(--risk-high)", critical: "var(--risk-crit)" }[level] || "var(--risk-med)";
}

function renderGauge(score, color) {
  const r = 36, c = 2 * Math.PI * r;
  const dash = (score / 100) * c;
  return `
    <div class="risk-gauge">
      <svg width="88" height="88" viewBox="0 0 88 88">
        <circle class="track" cx="44" cy="44" r="${r}"></circle>
        <circle class="fill" cx="44" cy="44" r="${r}"
          stroke="${color}"
          stroke-dasharray="${dash} ${c}"></circle>
      </svg>
      <div class="value">${score}</div>
    </div>`;
}

async function analyzeScam() {
  const text = document.getElementById("scamInput").value.trim();
  const resultEl = document.getElementById("scamResult");
  const btn = document.getElementById("scamAnalyzeBtn");
  if (!text) {
    resultEl.innerHTML = `<div class="error-box">Paste a transcript or message first.</div>`;
    return;
  }
  btn.disabled = true;
  btn.textContent = "Analysing…";
  resultEl.innerHTML = `<div class="empty-state"><div class="empty-glyph">◌</div><p>Running scam-pattern classifier…</p></div>`;

  try {
    const res = await fetch(`${API_BASE_URL}/api/scam/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Analysis failed.");
    const r = data.result;
    const color = riskColor(r.risk_level);

    resultEl.innerHTML = `
      <div class="risk-header">
        ${renderGauge(r.risk_score, color)}
        <div class="risk-meta">
          <div class="risk-label" style="color:${color}">${(r.risk_level || "").toUpperCase()} RISK</div>
          <div class="risk-sub">${r.scam_type || "Pattern classification"}</div>
        </div>
      </div>
      <div class="tag-row">
        <span class="tag">Impersonating: ${r.impersonated_entity || "N/A"}</span>
        <span class="tag">Confidence: ${r.confidence || "n/a"}</span>
      </div>
      <div class="section-label">Red flags detected</div>
      <ul class="flag-list">
        ${(r.red_flags || []).map(f => `<li>${escapeHtml(f)}</li>`).join("") || "<li>No specific red flags detected.</li>"}
      </ul>
      <div class="action-box"><strong>Recommended action:</strong> ${escapeHtml(r.recommended_action || "")}</div>
    `;
  } catch (e) {
    resultEl.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Analyse transcript";
  }
}
document.getElementById("scamAnalyzeBtn").addEventListener("click", analyzeScam);

// ================================================================
// FEATURE 2 — Counterfeit Currency Identification Agent
// ================================================================
let selectedFile = null;
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("currencyFile");
const dzEmpty = document.getElementById("dropzoneEmpty");
const dzPreview = document.getElementById("dropzonePreview");

dropzone.addEventListener("click", () => fileInput.click());
["dragover", "dragenter"].forEach(evt =>
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.add("dragover"); })
);
["dragleave", "drop"].forEach(evt =>
  dropzone.addEventListener(evt, e => { e.preventDefault(); dropzone.classList.remove("dragover"); })
);
dropzone.addEventListener("drop", e => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener("change", e => {
  const file = e.target.files[0];
  if (file) handleFile(file);
});

function handleFile(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    dzPreview.src = e.target.result;
    dzPreview.hidden = false;
    dzEmpty.hidden = true;
  };
  reader.readAsDataURL(file);
}

function featureBar(label, score, note) {
  return `
    <div class="feature-bar-row">
      <div class="feature-bar-top"><span class="fname">${label}</span><span class="fscore">${score}%</span></div>
      <div class="feature-bar-track"><div class="feature-bar-fill" style="width:${score}%"></div></div>
      <div class="feature-note">${note}</div>
    </div>`;
}

async function analyzeCurrency() {
  const resultEl = document.getElementById("currencyResult");
  const btn = document.getElementById("currencyAnalyzeBtn");
  if (!selectedFile) {
    resultEl.innerHTML = `<div class="error-box">Upload a note image first.</div>`;
    return;
  }
  btn.disabled = true;
  btn.textContent = "Scanning…";
  resultEl.innerHTML = `<div class="empty-state"><div class="empty-glyph">◌</div><p>Running computer-vision pipeline…</p></div>`;

  try {
    const formData = new FormData();
    formData.append("image", selectedFile);
    formData.append("denomination", document.getElementById("denomSelect").value);

    const res = await fetch(`${API_BASE_URL}/api/counterfeit/analyze`, { method: "POST", body: formData });
    const data = await res.json();
    if (!res.ok || !data.ok) throw new Error(data.error || "Analysis failed.");
    const r = data.result;

    const feats = r.features;
    resultEl.innerHTML = `
      <div class="verdict-banner ${r.alert_level === 'low' ? 'low' : r.alert_level === 'medium' ? 'medium' : 'high'}">
        <span>${escapeHtml(r.verdict)}</span>
        <span class="verdict-score">${r.authenticity_score}%</span>
      </div>
      ${featureBar("Print quality", feats.print_quality.score, feats.print_quality.note)}
      ${featureBar("Microprint density", feats.microprint_density.score, feats.microprint_density.note)}
      ${featureBar("Security thread signature", feats.security_thread.score, feats.security_thread.note)}
      ${featureBar("Colour consistency", feats.colour_consistency.score, feats.colour_consistency.note)}
      ${featureBar("Edge density / texture", feats.edge_density.score, feats.edge_density.note)}
      <div class="disclaimer">${escapeHtml(r.disclaimer)}</div>
    `;
  } catch (e) {
    resultEl.innerHTML = `<div class="error-box">${escapeHtml(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Run CV analysis";
  }
}
document.getElementById("currencyAnalyzeBtn").addEventListener("click", analyzeCurrency);

// ================================================================
// FEATURE 3 — Citizen Fraud Shield (chat)
// ================================================================
const chatLog = document.getElementById("chatLog");
const chatInput = document.getElementById("chatInput");
let chatHistory = [];

function appendMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `chat-msg ${role}`;
  wrap.innerHTML = `
    <div class="chat-avatar">${role === "user" ? "YOU" : "FS"}</div>
    <div class="chat-bubble">${escapeHtml(text)}</div>
  `;
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrap;
}

function appendTyping() {
  const wrap = document.createElement("div");
  wrap.className = "chat-msg assistant";
  wrap.id = "typingIndicator";
  wrap.innerHTML = `
    <div class="chat-avatar">FS</div>
    <div class="chat-bubble typing-dots"><span></span><span></span><span></span></div>
  `;
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function sendChat() {
  const message = chatInput.value.trim();
  if (!message) return;
  appendMessage("user", message);
  chatHistory.push({ role: "user", content: message });
  chatInput.value = "";
  appendTyping();

  const btn = document.getElementById("chatSendBtn");
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: chatHistory }),
    });
    const data = await res.json();
    document.getElementById("typingIndicator")?.remove();
    if (!res.ok || !data.ok) throw new Error(data.error || "Chat failed.");
    appendMessage("assistant", data.reply);
    chatHistory.push({ role: "assistant", content: data.reply });
  } catch (e) {
    document.getElementById("typingIndicator")?.remove();
    appendMessage("assistant", `Error: ${e.message}`);
  } finally {
    btn.disabled = false;
  }
}
document.getElementById("chatSendBtn").addEventListener("click", sendChat);
chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendChat();
  }
});

// ---------------- utils ----------------
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str ?? "";
  return div.innerHTML;
}
