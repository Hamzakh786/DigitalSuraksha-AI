import os
import traceback

from flask import Flask, request, jsonify
from dotenv import load_dotenv

from grok_client import chat_completion, extract_json, GrokError
from cv_analysis import analyze_note

load_dotenv()

app = Flask(__name__)

MAX_UPLOAD_MB = 8
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Minimal manual CORS (no extra dependency needed) so the static frontend
# can be opened straight from the file system or a different dev port.
# ---------------------------------------------------------------------------
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204


# ---------------------------------------------------------------------------
# Feature 1: Digital Arrest Scam Detection & Alerting
# ---------------------------------------------------------------------------
SCAM_SYSTEM_PROMPT = """You are a fraud-analysis engine used by an Indian law-enforcement \
digital-safety platform. You analyse a transcript / description of a phone call, video \
call, SMS, or WhatsApp message and assess the likelihood it is part of a "digital arrest" \
scam or related impersonation fraud (fraudsters posing as CBI, ED, Customs, police, TRAI, \
RBI, courier companies, etc., pressuring a victim with fake legal threats, demanding money \
transfers, insisting on secrecy, or staging a fake video "arrest").

Return ONLY a JSON object with this exact shape, no prose outside the JSON:
{
  "risk_score": <integer 0-100>,
  "risk_level": "low" | "medium" | "high" | "critical",
  "scam_type": "<short label, e.g. 'Digital Arrest Impersonation', 'Courier/Parcel Scam', 'Not a scam pattern', etc.>",
  "red_flags": ["<short flag>", ...],
  "impersonated_entity": "<e.g. CBI / ED / Customs / Courier / None detected>",
  "recommended_action": "<2-3 sentence plain-language guidance for the citizen or telecom/bank operator receiving this alert>",
  "confidence": "<low|medium|high>"
}

Base risk_score on concrete signals present in the text: claims of arrest warrants, demands \
for secrecy/isolation from family, urgency and threats, requests for money/OTP/gift cards, \
fake video calls with uniforms, mention of parcels with contraband, insistence on staying on \
a call continuously, requests to install remote-access apps, etc. If the text shows no such \
signals, score it low and say so plainly."""


@app.route("/api/scam/analyze", methods=["POST"])
def scam_analyze():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Provide 'text' with the call/message transcript."}), 400
    if len(text) > 6000:
        text = text[:6000]

    try:
        raw = chat_completion(
            messages=[
                {"role": "system", "content": SCAM_SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyse this:\n\n{text}"},
            ],
            temperature=0.1,
            max_tokens=600,
            json_mode=True,
        )
        result = extract_json(raw)
        return jsonify({"ok": True, "result": result})
    except GrokError as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Unexpected server error: {e}"}), 500


# ---------------------------------------------------------------------------
# Feature 2: Counterfeit Currency Identification Agent (Computer Vision)
# ---------------------------------------------------------------------------
@app.route("/api/counterfeit/analyze", methods=["POST"])
def counterfeit_analyze():
    if "image" not in request.files:
        return jsonify({"error": "Upload an image file under the 'image' field."}), 400

    file = request.files["image"]
    denomination = request.form.get("denomination", "auto")
    image_bytes = file.read()
    if not image_bytes:
        return jsonify({"error": "Empty image file."}), 400

    try:
        result = analyze_note(image_bytes, denomination=denomination)
        return jsonify({"ok": True, "result": result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Unexpected server error: {e}"}), 500


# ---------------------------------------------------------------------------
# Feature 3: Citizen Fraud Shield (multi-turn conversational triage)
# ---------------------------------------------------------------------------
FRAUD_SHIELD_SYSTEM_PROMPT = """You are "Fraud Shield", a calm, plain-language citizen-facing \
assistant on an Indian digital-public-safety platform. Citizens describe a suspicious call, \
SMS, payment request, or online message, and you help them assess risk in real time.

Rules:
- Ask at most one short clarifying question at a time if you genuinely need more detail, \
otherwise give your assessment directly.
- Always be concrete: name the likely scam pattern if there is one (digital arrest scam, \
KYC/bank update phishing, courier/parcel scam, fake job offer, loan-app harassment, \
investment/trading fraud, romance scam, sextortion, OTP fraud, etc.).
- Never ask the citizen to share OTPs, passwords, or full card numbers with you.
- End every substantive response with clear next steps, and when risk is medium/high, tell \
them to call the National Cyber Crime Helpline 1930 or report at cybercrime.gov.in, and to \
never share OTPs or move money while pressured.
- Keep responses short: 3-6 sentences, everyday language, no markdown headers.
- If the citizen's message does not describe a fraud situation at all, gently say this tool \
is for assessing suspicious calls/messages/payments and ask what happened."""


@app.route("/api/chat", methods=["POST"])
def fraud_shield_chat():
    data = request.get_json(silent=True) or {}
    history = data.get("history") or []
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Provide 'message'."}), 400

    messages = [{"role": "system", "content": FRAUD_SHIELD_SYSTEM_PROMPT}]
    for turn in history[-10:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    try:
        reply = chat_completion(messages=messages, temperature=0.4, max_tokens=400)
        return jsonify({"ok": True, "reply": reply})
    except GrokError as e:
        return jsonify({"ok": False, "error": str(e)}), 502
    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": f"Unexpected server error: {e}"}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "digital-safety-shield-backend"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
