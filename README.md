# CivicVoice AI – Multilingual Voice-Based Civic Complaint Assistant

## Overview

CivicVoice AI is a multilingual voice-based civic complaint management prototype designed to make reporting local civic issues easier and more accessible.

Citizens can report problems using voice input instead of manually writing lengthy complaints. The system converts speech into text, identifies the complaint category and priority, generates a complaint record, and provides a voice confirmation.

An administrative dashboard helps officials or administrators review complaints, monitor their status, identify duplicate reports, and analyse complaint trends.

## Problem Statement

Citizens often face difficulties reporting civic issues such as damaged roads, traffic problems, garbage accumulation, streetlight failures, and water leakage. Traditional complaint processes can be time-consuming and inaccessible to people who are uncomfortable with text-based forms.

CivicVoice AI aims to simplify this process through voice-based interaction and data-driven complaint monitoring.

## Key Features

### 1. Citizen Voice Interface
- Voice-based complaint submission.
- English and Kannada speech input options.
- Speech-to-text conversion using Gnani AI Prisma STT.
- Automatic complaint category identification.
- Priority classification based on urgency-related keywords.
- Voice confirmation using Gnani AI Timbre TTS.

### 2. Admin Dashboard
- Persistent complaint storage using Google Drive CSV.
- Complaint search by ID, description, and location.
- Category and status filtering.
- Complaint status updates.
- Audit logging of administrative actions.
- Duplicate complaint detection using text similarity.
- SLA monitoring for pending and in-progress complaints.
- Visual analytics using Plotly charts.
- Complaint and audit report CSV exports.

### 3. Data Analytics
- Complaint distribution by category.
- Priority-level analysis.
- Area-wise complaint analysis.
- SLA monitoring and overdue complaint identification.
- Duplicate complaint insights.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| User Interface | Gradio |
| Speech-to-Text | Gnani AI Prisma STT |
| Text-to-Speech | Gnani AI Timbre TTS |
| Data Processing | Pandas |
| Data Visualization | Plotly |
| Database Storage | CSV with Google Drive |
| Development Environment | Google Colab |

## System Workflow

1. Citizen records or uploads a voice complaint.
2. Gnani AI Prisma STT converts speech into text.
3. The system identifies the complaint category and priority using keyword-based rules.
4. A complaint record is generated with a unique ID and timestamp.
5. Gnani AI Timbre TTS generates a voice confirmation.
6. Administrators can review and manage complaints through the dashboard.
7. Complaint data is analysed through dashboard visualizations and reports.

## Project Structure

```text
CivicVoice-AI/
│
├── README.md
├── CivicVoice_Solution_Pitch.pdf
├── CivicVoice_Citizen_App.ipynb
└── CivicVoice_Admin_Dashboard.ipynb
```

*The notebook filenames above are suggested names. Update them to match the actual files uploaded.*

## Setup and Execution

1. Open the project notebooks using Google Colab.
2. Install the required Python dependencies specified in the notebooks.
3. Configure your Gnani AI API key securely using Google Colab Secrets.
4. Mount Google Drive when running the administrative dashboard.
5. Execute the notebook cells in sequence.
6. Open the generated Gradio interface to interact with the application.

**Important:** Never upload API keys, credentials, or private complaint records to this public repository.

## Current Implementation Notes

- Complaint categorization and priority assignment currently use keyword-based rules.
- Duplicate detection uses text similarity and category/location matching.
- SLA thresholds are configurable prototype settings, not official government service standards.
- The current prototype supports English and Kannada speech input.
- Voice confirmation has been tested using the configured Hindi TTS voice.
- The system is a demonstration prototype. It does not directly submit complaints to government authorities.

## Future Enhancements

- Integrate an AI-powered reasoning model for improved complaint understanding.
- Expand multilingual speech recognition and voice responses.
- Connect citizen submissions and the admin dashboard through a unified live database.
- Introduce geolocation-based complaint mapping.
- Add role-based authentication and secure access control.
- Explore integration with official civic complaint platforms.

## Project Documentation

Refer to [`CivicVoice_Solution_Pitch.pdf`](CivicVoice_Solution_Pitch.pdf) for the one-page project solution pitch.

## Disclaimer

CivicVoice AI is an independent prototype developed for demonstration and innovation purposes. It is not an official government complaint portal.
