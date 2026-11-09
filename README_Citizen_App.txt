# CivicVoice AI — Citizen App deliverables

## Files
- `CivicVoice_Citizen_App.ipynb` — Google Colab notebook.
- `CivicVoice_Citizen_App.py` — matching Python source.
- `requirements.txt` — dependencies.
- `CivicVoice_Demo_Video_Storyboard.md` — 2:30 demo storyboard and narration.

## Before running
1. In Google Colab, open Secrets and add `GNANI_API_KEY`. Enable notebook access.
2. Use the same Google account/Drive as the Admin Dashboard.
3. Run notebook cells in order.
4. Grant Google Drive access when prompted.
5. Record a test complaint and verify the new row appears in the shared Drive CSV and Admin Dashboard.

## Important implementation notes
- Complaint category and priority are assigned using keyword rules; this is not a trained AI classifier.
- STT uses Gnani Prisma through `gnani-vachana`.
- Voice confirmation uses Gnani Timbre configured for Hindi (`hi-IN`) with the Nalini voice.
- The notebook preserves existing complaint rows and adds the `Location` column if missing.
- Do not commit API keys, private complaint CSVs, or audit logs to GitHub.
- The Admin Dashboard's audit log is maintained by the Admin Dashboard; this Citizen App does not write administrative audit events.
- The app does not submit complaints to government authorities. It records them for review in the prototype database.
