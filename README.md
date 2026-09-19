<div align="center">

# 🌾 KrishiMitra
### AI-Powered Smart Farming Assistant

**Submission for SYNAPTRIX AI Hackathon**

[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Claude](https://img.shields.io/badge/Anthropic-Claude-000000)](https://www.anthropic.com/)
[![HuggingFace](https://img.shields.io/badge/HuggingFace-Inference_API-FFD21E?logo=huggingface)](https://huggingface.co/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Helping farmers make **AI-driven agricultural decisions** through crop disease detection, weather intelligence, market analysis, and yield prediction.

</div>

---

# 📌 Problem Statement Chosen

**Domain:** AgriSense

**Problem Statement:** Build an AI-powered farm companion that acts like an agronomist, a market analyst, and a weather advisor all in one — diagnosing crop health from a photo, explaining the diagnosis in plain conversational language, and helping the farmer decide not just what's wrong with the crop, but when and where to sell it for the best possible return.

---

# 👥 Team

**Team Name:** EchoNull

- Shreya Jha
- Soumya Kumari
- Samhitha D J

---

# 🌱 Our Solution

KrishiMitra is an AI farming companion built around a simple flow: a farmer uploads or photographs a crop leaf, and the platform detects the disease, estimates severity, and explains it in plain language with practical next steps. It then acts as a market agent — combining live weather, price trends, and crop perishability to recommend Sell Now or Hold, with full reasoning, not a black-box output. Beyond a single scan, farmers can run a multi-photo field scan for an aggregated field health score, ask free-form questions to an AI assistant, get weather-aware advice localized to their exact state and city (auto-detected via geolocation), and interact by voice instead of typing. The goal is a tool that works the way a smallholder farmer with a basic smartphone actually operates — fast, visual, and explainable.

---

# 🤖 AI Component

- **What AI is used:** Hugging Face Inference API (MobileNetV2 plant-disease classification model — `linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification`) for computer vision, and the Anthropic Claude API for agentic reasoning, natural-language explanation, translation, and Q&A.
- **What it does in the app:**
  - Classifies crop disease from a leaf photo with a confidence score and severity level
  - Aggregates results across multiple photos into a single field health score
  - Uses Claude with real tool-calling (price trend, live weather, crop perishability) to reason through a Sell Now / Hold recommendation and explain *why*
  - Generates a plain-language diagnosis explanation and treatment guidance from the raw classification output
  - Translates result text into Hindi and other regional languages on request
  - Answers free-form farmer questions in a Community Q&A tab
- **Why we chose this approach:** A pretrained vision model gives reliable, fast disease classification without needing our own training data or GPU budget within an 8-hour build window. Claude's tool-calling lets us combine multiple live data sources (weather, price, perishability) into a single explainable recommendation rather than a hardcoded rule, which is what a real agronomist's judgment looks like — and reusing one Claude integration across explanation, translation, and Q&A kept the AI surface area simple to build reliably under time pressure.

---

# ⚙️ Tech Stack

| Layer | Technology |
|---------|------------|
| Frontend | React 19, Vite, React Router, Axios, Lucide React |
| Backend | FastAPI, Python, Uvicorn |
| AI/ML | Anthropic Claude API (agentic reasoning, explanation, translation, Q&A), Hugging Face Inference API (MobileNetV2 disease classification) |
| Database/Storage | In-memory storage on the backend (no persistent database) — used for outbreak-map scan logging and Community Q&A history; resets on server restart |
| Weather | OpenWeatherMap API (current weather + reverse geocoding for all 28 Indian states, 8 union territories, and free-text city input) |
| Voice | Browser-native Web Speech API (no key required) |
| Deployment | Vercel (frontend) + Render (backend) |
| Version Control | GitHub |

---

# ✨ Features Implemented

## Core Requirements
- 🌿 **AI Disease Detection** — upload or camera-capture a leaf photo, get disease name, confidence score, severity, and AI-generated treatment guidance
- 💬 **AI Chatbot Explanation** — Claude explains each diagnosis in plain language with practical next steps, generated per-result rather than templated
- 📈 **Market Price Trend View** — price trend data across 30+ Indian crops
- 🧠 **Smart Sell/Hold Advisor** — Claude agent using real tool-calling across price trend, live weather, and perishability to recommend Sell Now or Hold with full reasoning
- 🎙️ **Voice Input** — speak instead of type on the Market Advisor, Yield Loss, Community Q&A, and Disease Detection (optional symptom notes) forms

## Bonus Features Attempted
- 📸 **Multi-Photo Field Scan** — analyze several leaf photos at once, aggregated into a single field health score with a disease breakdown
- 🌾 **Yield Loss Estimator** — projects tons lost, revenue impact, and potential savings from disease severity and affected area
- 🗺️ **Community Outbreak Map** — logs scan results by region to flag where diseases are appearing/spreading (simulated, in-memory)
- 🌐 **Multilingual Support** — Claude translates diagnosis, advisor reasoning, and yield-loss results into Hindi and other regional languages
- ❓ **Community Q&A** — farmers can ask open-ended questions, answered by Claude as an agronomist persona
- 💚 **WhatsApp-Bot Concept Mockup** — a visual mockup of how KrishiMitra could be delivered via WhatsApp (concept only, no live Twilio integration)
- 📍 **Geolocation Auto-Detect** — browser geolocation + reverse geocoding auto-fills state and city for weather/advisor queries
- 🥬 **Expanded Crop Database** — 30+ Indian crops including rice, wheat, maize, tomato, onion, potato, cotton, sugarcane, mango, turmeric, and more

---

# 🚀 Live Demo

**Frontend:** https://krishi-mitra-agrisense.vercel.app/
**Backend:** https://krishimitra-agrisense.onrender.com/

---

# 📂 Project Structure

```
frontend/
│
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   └── assets/

backend/
│
├── app.py
├── crop_detector.py
├── claude_agent.py
├── tools.py
├── requirements.txt
└── .env
```

---

# 🛠️ How to Run This Project

## Clone the repo
```bash
git clone https://github.com/ShreyaJ-27/KrishiMitra-agrisense
```

## Backend
```bash
cd backend

python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt

# Copy the example env file and fill in your own keys
cp .example.env .env

uvicorn app:app --reload
```

## Frontend
```bash
cd frontend

npm install

# Copy the example env file
cp .example.env .env

npm run dev
```

---

# 🔑 API Keys / Environment Variables

API keys are never committed to this repo — `.env` is listed in `.gitignore`. Example env files (`.example.env`) are committed with variable names only, so judges know exactly what to fill in.

## Backend — `backend/.env`
```env
ANTHROPIC_API_KEY= your_api_key
HF_TOKEN=your_hf_token
HF_MODEL=linkanjarad/mobilenet_v2_1.0_224-plant-disease-identification
WEATHER_API_KEY= your_api_key
```

## Frontend — `frontend/.env`
```env
VITE_API_URL=http://localhost:8000
```

> **Note:** All AI-related bonus features (multilingual translation, diagnosis explanation, Community Q&A, voice input) reuse the `ANTHROPIC_API_KEY` and `HF_TOKEN` above — no additional keys are required beyond the three listed.

---

# 📸 Screenshots

| Landing Page | Disease Detection |
|--------------|-------------------|
| ![Landing Page](screenshots/landingpage.png) | ![Disease Detection](screenshots/disease_detection.png) |

| Claude Market Advisor  | Yield Loss Estimator |
|------------------------|-------------------------|
| ![Claude Market Advisor](screenshots/market_advisor.png) | ![Yield Loss Estimator](screenshots/yield_loss.png) |

# 🔮 Future Scope

- Farmer authentication and personal dashboard with crop history
- Government scheme recommendations
- Native mobile application
- IoT sensor and satellite monitoring integration
- Offline AI support for low-connectivity areas
- Real-time mandi price APIs (current price data is illustrative)
- Persistent database for outbreak map and Q&A history (currently in-memory/session-based)

---

# 📄 License

This project is licensed under the **MIT License**.

---

<div align="center">

### 🌾 Empowering Farmers Through Artificial Intelligence

**Built with ❤️ by Team EchoNull**

</div>
