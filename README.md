# Raksha Grid — AI for Digital Public Safety (Prototype)

A working prototype for the "AI for Digital Public Safety: Defeating Counterfeiting, Fraud &
Digital Arrest Scams" challenge, scoped to **3 of the suggested build areas**, chosen because
they're demoable end-to-end with a single LLM (Grok) + classical computer vision, no training
data or agency integrations required:

1. **Digital Arrest Scam Detection & Alerting** — paste a call/SMS/WhatsApp transcript, get a
   risk score, red flags, impersonated-entity guess, and recommended action (Grok LLM, JSON
   structured output).
2. **Counterfeit Currency Identification Agent** — upload a note photo, get a transparent,
   inspectable computer-vision score (print sharpness, microprint density via FFT, security
   thread signature via Hough line detection, colour-band consistency, edge density).
3. **Citizen Fraud Shield** — a guided chat that triages a suspicious call/SMS/payment
   situation in plain language and points to the 1930 helpline / cybercrime.gov.in when risk
   is medium/high (Grok LLM, multi-turn).

> This is a hackathon-grade prototype: the CV pipeline is a heuristic (no proprietary
> genuine-note dataset was available), and the LLM prompts are tuned for demo quality, not
> production accuracy. Everything is clearly labelled as such in the API responses and UI.

---

## Project layout

```
digital-safety-shield/
├── backend/
│   ├── app.py                # Flask API — 3 endpoints + health check
│   ├── grok_client.py        # xAI (Grok) chat-completions wrapper
│   ├── cv_analysis.py        # OpenCV counterfeit-detection heuristics
│   ├── requirements.txt
│   └── .env.example          # copy to .env and add your GROK_API_KEY
├── frontend/
│   ├── index.html            # 3-tab single-page app
│   ├── style.css              # "Raksha Grid" command-centre theme
│   ├── app.js                 # wires the UI to the backend
│   └── config.js               # backend base URL
└── docs/
    └── architecture-diagram.svg   # system architecture (open in a browser or Illustrator)
```

## Architecture

See `docs/architecture-diagram.svg` for the full system diagram (client → Flask API →
Grok LLM / OpenCV pipeline → xAI). In short:

- The frontend calls three Flask endpoints directly.
- `/api/scam/analyze` and `/api/chat` both go through `grok_client.py` to the xAI Grok API.
- `/api/counterfeit/analyze` runs entirely locally through `cv_analysis.py` — no external
  API call, so it works even without a Grok key.

## 1. Backend setup

```bash
cd backend
python3 -m venv venv && source venv/bin/activate   # optional but recommended
pip install -r requirements.txt

cp .env.example .env
# then edit .env and set:
#   GROK_API_KEY=your_real_xai_key
# (get one at https://console.x.ai)

python3 app.py
# -> Flask dev server on http://localhost:5000
```

Health check: `curl http://localhost:5000/api/health`

### Endpoints

| Method | Path                      | Purpose                                             |
|--------|---------------------------|------------------------------------------------------|
| POST   | `/api/scam/analyze`       | `{ "text": "<transcript>" }` → scam risk JSON        |
| POST   | `/api/counterfeit/analyze`| multipart `image` (+ optional `denomination`) → CV JSON |
| POST   | `/api/chat`                | `{ "message": "...", "history": [...] }` → chat reply |
| GET    | `/api/health`               | liveness check                                       |

## 2. Frontend setup

No build step — it's plain HTML/CSS/JS. Just open it or serve it statically:

```bash
cd frontend
python3 -m http.server 8080
# then open http://localhost:8080 in a browser
```

If your backend runs somewhere other than `http://localhost:5000`, edit
`frontend/config.js` and update `API_BASE_URL`.

## 3. Using Grok (xAI)

`backend/grok_client.py` calls the OpenAI-compatible endpoint
`https://api.x.ai/v1/chat/completions` with your `GROK_API_KEY`. The model name is
configurable via `GROK_MODEL` in `.env` (defaults to `grok-4-latest`) — change it to whatever
model your xAI account has access to if needed.

## Notes on the computer-vision agent

`cv_analysis.py` intentionally avoids a black-box "genuine/fake" flag. It runs five
inspectable signals and combines them with transparent weights:

- **Print quality** — Laplacian variance (blur detection)
- **Microprint density** — FFT high-frequency energy ratio in a central crop
- **Security-thread signature** — Hough line detection tuned for a thin vertical line
- **Colour consistency** — dominant hue vs. an expected band for the declared denomination
- **Edge density** — coarse Canny edge-density texture check

Each is returned with its own score and a plain-language note, so a bank teller or officer
can see *why* a note was flagged rather than trusting an opaque verdict. Swapping in a
trained CNN classifier later is a drop-in replacement for `analyze_note()`.

## Suggested next steps (out of scope for this prototype)

- Real labelled note dataset + trained CV/CNN model for the counterfeit agent
- Telecom/bank integration for real-time call metadata (Feature 1's "flags active scam
  sessions to telecom providers" capability)
- Persistent case storage, auth, and the fraud-network graph / geospatial layers from the
  full brief
