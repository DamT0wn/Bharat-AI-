from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import google.generativeai as genai
import os, re, requests
from dotenv import load_dotenv
import warnings

# Suppress deprecation warning
warnings.filterwarnings("ignore", category=FutureWarning)

# ----------------------------
# CONFIG
# ----------------------------
load_dotenv()

GEMINI_KEY = os.getenv("GEMINI_API_KEY")
SECRET_KEY = os.getenv("SECRET_API_KEY")

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel("models/gemini-flash-latest")
else:
    print("Warning: GEMINI_API_KEY not found in .env")
    model = None

GUVI_CALLBACK = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"

app = FastAPI()

# In-memory session store
session_data = {}

# ----------------------------
# HEALTH CHECK & INFO ENDPOINTS
# ----------------------------
@app.get("/")
def root():
    # Serve the HTML frontend
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_file):
        return FileResponse(static_file, media_type="text/html")
    return {
        "status": "running",
        "service": "AI Scam Honeypot Agent",
        "endpoints": {
            "health": "GET /health",
            "api_docs": "GET /docs",
            "honeypot": "POST /honeypot"
        }
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "AI Scam Honeypot Agent"}

# ----------------------------
# INPUT SCHEMA
# ----------------------------
class ChatMessage(BaseModel):
    sender: str
    text: str
    timestamp: int


class RequestPayload(BaseModel):
    sessionId: str
    message: ChatMessage
    conversationHistory: List[ChatMessage] = []
    metadata: Optional[dict] = None


# ----------------------------
# INTELLIGENCE EXTRACTION
# ----------------------------
def extract_intel(text):
    return {
        "bankAccounts": re.findall(r"\b\d{9,18}\b", text),
        "upiIds": re.findall(r"[a-zA-Z0-9.\-_]+@[a-zA-Z]+", text),
        "phishingLinks": re.findall(r"https?://\S+", text),
        "phoneNumbers": re.findall(r"\+91\d{10}", text),
        "suspiciousKeywords": [
            word for word in ["urgent", "verify", "blocked", "suspend"]
            if word in text.lower()
        ]
    }


# ----------------------------
# SCAM DETECTION LOGIC
# ----------------------------
def detect_scam(msg):
    scam_signals = [
        "blocked", "verify", "urgent", "upi",
        "account suspended", "send money", "click link"
    ]
    return any(word in msg.lower() for word in scam_signals)


# ----------------------------
# AI AGENT RESPONSE
# ----------------------------
def agent_reply(history_text):
    prompt = f"""
You are an autonomous AI Honeypot Agent.

Role:
- Act like a normal Indian user (victim persona)
- Never reveal scam detection
- Continue conversation naturally
- Try to extract UPI IDs, bank accounts, links

Conversation so far:
{history_text}

Reply with ONE realistic message only.
"""

    response = model.generate_content(prompt)
    return response.text.strip()


# ----------------------------
# FINAL CALLBACK
# ----------------------------
def send_final_callback(sessionId, intel, total_turns):
    payload = {
        "sessionId": sessionId,
        "scamDetected": True,
        "totalMessagesExchanged": total_turns,
        "extractedIntelligence": intel,
        "agentNotes": "Scammer used urgency tactics and payment redirection"
    }

    try:
        requests.post(GUVI_CALLBACK, json=payload, timeout=5)
    except:
        print("GUVI callback failed (prototype safe)")


# ----------------------------
# MAIN API ENDPOINT
# ----------------------------
@app.post("/honeypot")
def honeypot_endpoint(
    req: RequestPayload,
    x_api_key: str = Header(None)
):
    # ✅ Authentication
    if x_api_key != SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")

    sessionId = req.sessionId

    # Build conversation text
    history_text = ""
    for msg in req.conversationHistory:
        history_text += f"{msg.sender}: {msg.text}\n"
    history_text += f"{req.message.sender}: {req.message.text}\n"

    total_turns = len(req.conversationHistory) + 1

    # Scam detection
    scamDetected = detect_scam(req.message.text)

    if not scamDetected:
        return {
            "scamDetected": False,
            "agentActivated": False,
            "reply": "Okay, thank you.",
            "engagementMetrics": {
                "sessionId": sessionId,
                "totalTurns": total_turns,
                "engagementActive": False
            },
            "extractedIntelligence": {}
        }

    # ✅ Agent Activated
    reply = agent_reply(history_text)

    # Extract intelligence
    intel = extract_intel(history_text)

    # Save session
    session_data[sessionId] = {
        "intel": intel,
        "turns": total_turns
    }

    # ✅ Callback after enough engagement
    if total_turns >= 5:
        send_final_callback(sessionId, intel, total_turns)

    return {
        "scamDetected": True,
        "agentActivated": True,
        "reply": reply,
        "engagementMetrics": {
            "sessionId": sessionId,
            "totalTurns": total_turns,
            "engagementActive": True
        },
        "extractedIntelligence": intel
    }
