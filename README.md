# 🛡️ Insurance Agent Sales Co-Pilot v2

> AI-powered real-time assistant that helps insurance agents analyze clients,
> recommend policies, coach on closing, and track performance.

---

## 🚀 Quick Start (3 steps)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the app
streamlit run app.py

# 3. Open in browser
# → http://localhost:8501
```

---

## 📁 Project Structure

```
insurance-copilot-v2/
│
├── app.py              # Main Streamlit dashboard (all 3 tabs)
├── ai_engine.py        # Client need analysis (AI + rule-based)
├── policy_engine.py    # Policy recommendation + commission engine
├── speech_engine.py    # Browser speech-to-text widget
├── session_manager.py  # Client session history + log
├── pdf_report.py       # PDF proposal generator
├── policies.json       # 16 policies across 6 categories
├── requirements.txt    # pip dependencies
└── README.md           # This file
```

---

## ✨ Features

### 🔍 Analyze Client Tab
- Paste or speak client conversation notes
- Detects intent: family, health, investment, child, business, term
- Shows top 1–5 policies ranked by profit score
- Commission estimate per deal
- Upsell/cross-sell suggestions

### 🎤 Speech-to-Text
- Browser microphone button (Chrome/Edge)
- Click mic → speak → copy transcript → paste
- No API key needed (uses browser WebSpeech API)

### 🤖 Claude AI Integration
- Enter your Anthropic API key in the sidebar
- AI analyzes client intent with rich context
- Returns: client profile, urgency, opening line, objections to expect
- Falls back to rule-based if no key provided

### 🎓 Live Coaching
- 3 actionable sales tips per client type
- AI-generated tips when Claude API is enabled
- Suggested opening line (AI mode)

### 🥊 Objection Handler
- Pre-built rebuttals for 5 common objections
- AI predicts which objections this specific client will raise

### 📄 PDF Report Export
- Generates professional client proposal PDF
- Includes: client details, needs analysis, recommended policies, financials
- Download with one click

### 📋 Session History
- Every analysis auto-saved to session_log.json
- View all past client sessions
- Shows client name, intent, top policy, premium value

### 📈 Performance Dashboard
- Sessions today / total sessions
- Total estimated commission
- Average profit score
- Intent distribution bar chart
- Per-session performance tracker

---

## ⚙️ Configuration

### Enable Claude AI (optional but recommended)
1. Get your API key: https://console.anthropic.com
2. Enter it in the sidebar under "Claude AI Integration"
3. The app automatically switches to AI analysis mode

### Enable PDF Export
```bash
pip install reportlab
```

### Enable Python Speech Recognition (optional)
```bash
pip install SpeechRecognition
# Mac: brew install portaudio && pip install pyaudio
# Windows: pip install pipwin && pipwin install pyaudio
```

---

## 📦 Policy Categories

| Category   | Policies | Example                    |
|------------|----------|----------------------------|
| Family     | 3        | Family Shield Plus         |
| Health     | 3        | Health Secure Pro          |
| Investment | 3        | Retirement Income Plus     |
| Child      | 2        | Child Genius Plan          |
| Business   | 2        | Business Continuity Shield |
| Term       | 2        | Term Life Max              |

---

## 🏆 Hackathon Demo Script

1. Open the app — show the clean dark dashboard
2. Click the 🎤 mic example → show speech-to-text widget
3. Click the 👨‍👩‍👧 Family example → hit Analyze
4. Walk through: intent detection → policies → coaching tips → objection handler
5. Add your API key → re-analyze with Claude AI mode
6. Show Session History tab → shows it was saved
7. Show Performance Dashboard
8. Download PDF report

---

Built for hackathon demo · Insurance Sales Co-Pilot v2.0
