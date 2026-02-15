# Minecraft Dashboard

A web dashboard for monitoring your Minecraft server.

## Step 1: Minimal Backend + Frontend

This is the initial version with a simple FastAPI backend and static frontend.

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)

### Installation

1. Clone this repository:
```bash
git clone https://github.com/anthonyi7/minecraft-dashboard.git
cd minecraft-dashboard
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

### Running the Dashboard

Start the FastAPI server:
```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The dashboard will be available at: http://localhost:8000

### API Endpoints

- `GET /api/healthz` - Health check endpoint (returns `{"ok": true}`)
- `GET /api/status` - Server status with mocked data

### Current Features (Step 1)

✅ FastAPI backend serving static files
✅ Health check endpoint
✅ Mocked server status endpoint
✅ Responsive dashboard UI
✅ Auto-refresh every 5 seconds

### Next Steps

- Step 2: Add RCON connection to real Minecraft server
- Step 3: Add SQLite database for player tracking
- Step 4: Add backup log monitoring
- Step 5: Containerize with Docker
- Step 6: Deploy to Kubernetes

## Project Structure

```
minecraft_dashboard/
├── app.py              # FastAPI backend
├── requirements.txt    # Python dependencies
├── static/
│   ├── index.html      # Dashboard UI
│   ├── styles.css      # Styling
│   └── app.js          # Frontend JavaScript
└── README.md           # This file
```

## Development

The server runs with auto-reload enabled, so any changes to `app.py` will automatically restart the server.

To stop the server, press `Ctrl+C` in the terminal.
