"""
CivicVoice AI — Citizen App
Multilingual voice-based civic complaint assistant using Gnani AI.

Colab setup:
1. Add GNANI_API_KEY under Colab Secrets.
2. Run this file in Google Colab (or copy its cells into a notebook).
3. Mount the same Google Drive account used by the Admin Dashboard.
4. Launch the Gradio interface.

The classifier below is rule/keyword-based, not a trained AI model.
Timbre confirmation is currently configured for Hindi (hi-IN).
"""

import os
import re
import uuid
import tempfile
import threading
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import gradio as gr

# ----------------------------- CONFIGURATION -----------------------------

DRIVE_FOLDER = "/content/drive/MyDrive/CivicVoice"
CSV_FILE = os.path.join(DRIVE_FOLDER, "civicvoice_complaints.csv")

EXPECTED_COLUMNS = [
    "Complaint ID", "Complaint", "Category", "Priority",
    "Status", "Reported At", "Location"
]

STT_LANGUAGE_CODES = {
    "English": "en-IN",
    "Kannada": "kn-IN",
}

STT_ENDPOINT = "https://api.vachana.ai/stt/v3"
TTS_ENDPOINT = "https://api.vachana.ai/api/v1/tts/inference"

DB_LOCK = threading.Lock()
GNANI_API_KEY = None
stt_client = None
DRIVE_READY = False


# ----------------------------- SECRETS / DRIVE -----------------------------

def get_api_key():
    """Read the key from Colab Secrets first, then environment variables."""
    key = None
    try:
        from google.colab import userdata
        key = userdata.get("GNANI_API_KEY")
    except Exception:
        pass
    if not key:
        key = os.environ.get("GNANI_API_KEY")
    if not key:
        raise RuntimeError(
            "GNANI_API_KEY was not found. In Google Colab, open Secrets "
            "(key icon), add GNANI_API_KEY, and enable notebook access."
        )
    return key


def mount_drive():
    """Mount Google Drive when running in Colab."""
    global DRIVE_READY
    try:
        from google.colab import drive
        drive.mount("/content/drive")
        os.makedirs(DRIVE_FOLDER, exist_ok=True)
        DRIVE_READY = True
        return "Google Drive mounted. Shared CivicVoice database is ready."
    except Exception as exc:
        DRIVE_READY = False
        return (
            "Google Drive could not be mounted. The app will not silently "
            "write to a separate database. Resolve Drive access and rerun. "
            f"Details: {type(exc).__name__}: {exc}"
        )


def initialize_stt():
    """Initialize the official Gnani Vachana STT SDK."""
    global GNANI_API_KEY, stt_client
    GNANI_API_KEY = get_api_key()
    try:
        from gnani.stt import GnaniSTTClient
        stt_client = GnaniSTTClient(api_key=GNANI_API_KEY)
    except Exception as exc:
        stt_client = None
        raise RuntimeError(
            "Could not initialize Gnani Prisma STT. Check gnani-vachana "
            f"installation and API key. Details: {type(exc).__name__}: {exc}"
        )


def ensure_database():
    """
    Create the shared database only when absent.
    Preserve all existing rows and add a missing Location column if needed.
    Writes atomically to reduce the chance of a partially-written CSV.
    """
    os.makedirs(DRIVE_FOLDER, exist_ok=True)

    if not os.path.exists(CSV_FILE) or os.path.getsize(CSV_FILE) == 0:
        empty = pd.DataFrame(columns=EXPECTED_COLUMNS)
        temp_path = CSV_FILE + ".tmp"
        empty.to_csv(temp_path, index=False)
        os.replace(temp_path, CSV_FILE)
        return

    try:
        df = pd.read_csv(CSV_FILE)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)

    changed = False
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
            changed = True

    # Keep the Admin Dashboard's expected column order, preserving any
    # additional columns rather than deleting them.
    ordered = EXPECTED_COLUMNS + [c for c in df.columns if c not in EXPECTED_COLUMNS]
    df = df[ordered]
    if changed or list(df.columns) != ordered:
        temp_path = CSV_FILE + ".tmp"
        df.to_csv(temp_path, index=False)
        os.replace(temp_path, CSV_FILE)


def read_complaints():
    ensure_database()
    try:
        df = pd.read_csv(CSV_FILE).fillna("")
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame(columns=EXPECTED_COLUMNS)
    for col in EXPECTED_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df


# ----------------------------- CLASSIFICATION -----------------------------

CATEGORY_KEYWORDS = {
    "Road Damage": [
        "pothole", "road", "damaged road", "broken road", "ಕುಳಿ",
        "ರಸ್ತೆ", "ಗುಂಡಿ", "ರಸ್ತೆ ಹಾಳಾಗಿದೆ"
    ],
    "Traffic": [
        "traffic", "signal", "congestion", "jam", "accident",
        "ಟ್ರಾಫಿಕ್", "ಸಂಚಾರ", "ಸಿಗ್ನಲ್", "ಅಪಘಾತ"
    ],
    "Streetlight": [
        "streetlight", "street light", "lamp", "dark road",
        "ಬೀದಿ ದೀಪ", "ದೀಪ", "ಲೈಟ್"
    ],
    "Water Leakage": [
        "water leak", "leakage", "pipe burst", "water supply",
        "ನೀರು", "ಸೋರಿಕೆ", "ಪೈಪ್"
    ],
    "Garbage": [
        "garbage", "waste", "trash", "rubbish", "dump",
        "ಕಸ", "ತ್ಯಾಜ್ಯ", "ಕಸ ಹಾಕಿದ್ದಾರೆ"
    ],
}

URGENT_KEYWORDS = [
    "emergency", "urgent", "dangerous", "danger", "accident",
    "severe", "ambulance", "life threatening", "ಆಪತ್ತು",
    "ಅಪಾಯಕಾರಿ", "ತುರ್ತು", "ಅಪಘಾತ"
]


def classify_complaint(transcript):
    """Transparent keyword-based category and priority classifier."""
    text = str(transcript or "").strip().lower()
    category = "Other Civic Issue"

    for candidate, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            category = candidate
            break

    priority = "High" if any(k.lower() in text for k in URGENT_KEYWORDS) else "Normal"
    return category, priority


def make_complaint_id():
    return "CV-" + datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:6].upper()


# ----------------------------- GNANI STT / TTS -----------------------------

def transcribe_audio(audio_path, language_label):
    if not audio_path:
        raise ValueError("Please record audio or upload an audio file.")
    if stt_client is None:
        initialize_stt()

    language_code = STT_LANGUAGE_CODES.get(language_label)
    if not language_code:
        raise ValueError("Please select English or Kannada.")

    result = stt_client.transcribe(audio_path, language_code=language_code)

    if isinstance(result, dict):
        transcript = (
            result.get("text")
            or result.get("transcript")
            or result.get("data", {}).get("text")
        )
    else:
        transcript = getattr(result, "text", None) or str(result)

    transcript = str(transcript or "").strip()
    if not transcript:
        raise RuntimeError("No speech was detected. Please try recording again.")
    return transcript


def generate_voice_confirmation(text):
    """Generate Hindi confirmation audio using the previously tested Timbre setup."""
    key = GNANI_API_KEY or get_api_key()
    payload = {
        "text": text,
        "voice": "Nalini",
        "model": "timbre-v2.5",
        "language": "hi-IN",
        "speed": 1,
        "audio_config": {
            "encoding": "linear_pcm",
            "container": "wav",
            "num_channels": 1,
            "sample_rate": 48000,
            "sample_width": 2
        }
    }
    response = requests.post(
        TTS_ENDPOINT,
        headers={"Content-Type": "application/json", "X-API-Key-ID": key},
        json=payload,
        timeout=60
    )
    response.raise_for_status()

    content_type = response.headers.get("Content-Type", "").lower()
    if "audio" not in content_type and not response.content.startswith(b"RIFF"):
        raise RuntimeError("TTS response was not a WAV/audio file.")

    fd, audio_file = tempfile.mkstemp(prefix="civicvoice_confirmation_", suffix=".wav")
    with os.fdopen(fd, "wb") as f:
        f.write(response.content)
    return audio_file


# ----------------------------- COMPLAINT REGISTRATION -----------------------------

def register_complaint(transcript, location):
    transcript = str(transcript or "").strip()
    location = str(location or "").strip()

    if len(transcript) < 4:
        raise ValueError("The complaint text is too short. Please record it again.")
    if not DRIVE_READY:
        raise RuntimeError(
            "Google Drive is not mounted. Mount the same Drive used by the "
            "Admin Dashboard before registering complaints."
        )

    category, priority = classify_complaint(transcript)
    complaint_id = make_complaint_id()
    reported_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = {
        "Complaint ID": complaint_id,
        "Complaint": transcript,
        "Category": category,
        "Priority": priority,
        "Status": "Pending Review",
        "Reported At": reported_at,
        "Location": location
    }

    # Serialize this app's writes and re-read immediately before appending.
    # This avoids stale in-memory data overwriting newer Admin/Citizen rows.
    with DB_LOCK:
        df = read_complaints()
        if complaint_id in df["Complaint ID"].astype(str).values:
            raise RuntimeError("A complaint with this ID already exists. Please retry.")
        updated = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
        temp_path = CSV_FILE + ".tmp"
        updated.to_csv(temp_path, index=False)
        os.replace(temp_path, CSV_FILE)

    return row


def recent_history(limit=10):
    df = read_complaints()
    if df.empty:
        return pd.DataFrame(columns=EXPECTED_COLUMNS)
    return df[EXPECTED_COLUMNS].tail(limit).iloc[::-1].reset_index(drop=True)


# ----------------------------- GRADIO CALLBACK -----------------------------

def submit_complaint(audio_path, language, location):
    try:
        transcript = transcribe_audio(audio_path, language)
        row = register_complaint(transcript, location)

        confirmation_text = (
            f"आपकी शिकायत दर्ज कर ली गई है। "
            f"आपकी शिकायत संख्या {row['Complaint ID']} है। "
            f"स्थिति: समीक्षा के लिए लंबित।"
        )
        audio_confirmation = None
        tts_status = "Voice confirmation could not be generated."
        try:
            audio_confirmation = generate_voice_confirmation(confirmation_text)
            tts_status = "Hindi voice confirmation generated."
        except Exception as tts_exc:
            tts_status = f"Complaint saved; voice confirmation unavailable: {type(tts_exc).__name__}"

        details = (
            f"### Complaint registered successfully\n"
            f"- **Complaint ID:** `{row['Complaint ID']}`\n"
            f"- **Category:** {row['Category']}\n"
            f"- **Priority:** {row['Priority']}\n"
            f"- **Status:** {row['Status']}\n"
            f"- **Location:** {row['Location'] or 'Not provided'}\n"
            f"- **Reported at:** {row['Reported At']}\n\n"
            f"{tts_status}"
        )
        return transcript, details, audio_confirmation, recent_history()
    except Exception as exc:
        error = f"**Could not register complaint:** {type(exc).__name__}: {exc}"
        return "", error, None, recent_history()


# ----------------------------- STARTUP -----------------------------

def startup():
    drive_message = mount_drive()
    if DRIVE_READY:
        ensure_database()
    key_message = "Gnani API key is configured." if os.environ.get("GNANI_API_KEY") else (
        "Add GNANI_API_KEY in Colab Secrets before using live STT/TTS."
    )
    try:
        # Do not expose the key; only report whether initialization worked.
        initialize_stt()
        key_message = "Gnani Prisma STT initialized successfully."
    except Exception as exc:
        key_message = f"STT not initialized yet: {type(exc).__name__}: {exc}"
    return drive_message + "\n" + key_message


with gr.Blocks(theme=gr.themes.Soft(), title="CivicVoice AI — Citizen App") as demo:
    gr.Markdown(
        """
        # CivicVoice AI
        ### Give every civic issue a voice.
        Report local civic problems using English or Kannada voice input.
        """
    )
    with gr.Row():
        language = gr.Dropdown(
            choices=["English", "Kannada"],
            value="English",
            label="Complaint language"
        )
        location = gr.Textbox(
            label="Location / Area",
            placeholder="Example: RNSIT Main Road, Bengaluru"
        )

    audio = gr.Audio(
        sources=["microphone", "upload"],
        type="filepath",
        label="Record or upload your complaint"
    )
    submit = gr.Button("Submit Civic Complaint", variant="primary")
    transcript_output = gr.Textbox(label="Recognised speech", lines=4)
    result_output = gr.Markdown(label="Registration result")
    audio_output = gr.Audio(label="Voice confirmation", type="filepath")
    history_output = gr.Dataframe(
        headers=EXPECTED_COLUMNS,
        label="Recent complaints",
        interactive=False
    )
    status_output = gr.Textbox(label="System status", interactive=False)
    refresh = gr.Button("Refresh complaint history")

    submit.click(
        fn=submit_complaint,
        inputs=[audio, language, location],
        outputs=[transcript_output, result_output, audio_output, history_output]
    )
    refresh.click(fn=recent_history, inputs=None, outputs=history_output)
    demo.load(fn=startup, inputs=None, outputs=status_output)


if __name__ == "__main__":
    demo.launch(share=True, debug=True)
