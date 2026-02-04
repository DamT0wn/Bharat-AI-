import streamlit as st
import requests
import time

st.title("🛡 AI Scam Honeypot Agent")

API_KEY = "AIzaSyCeeAc7BHRkSJYGzQk62IEJiK8oX_1iYeI"
session_id = f"session_{int(time.time())}"

st.write(f"**Session ID:** {session_id}")

msg = st.text_area("Paste scam message", height=150)

if st.button("Test Honeypot Agent"):
    if msg:
        payload = {
            "sessionId": session_id,
            "message": {
                "sender": "scammer",
                "text": msg,
                "timestamp": int(time.time())
            },
            "conversationHistory": []
        }
        
        headers = {"x-api-key": API_KEY}
        
        try:
            r = requests.post(
                "http://127.0.0.1:8000/honeypot",
                json=payload,
                headers=headers
            )
            st.json(r.json())
        except Exception as e:
            st.error(f"Error: {str(e)}")
    else:
        st.warning("Please enter a message")
