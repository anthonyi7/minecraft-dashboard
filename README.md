# Minecraft Dashboard

A real-time web dashboard for monitoring your Minecraft server with RCON integration and intelligent caching.

![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-green)

## Features

- **Real-time Monitoring** - Live player count and server status via RCON
- **Background Polling** - Efficient caching system polls server every 10 seconds
- **Instant API Responses** - Sub-millisecond response times from in-memory cache
- **Resilient** - Shows last known good data if RCON temporarily fails
- **Scalable** - Multiple dashboards share the same cache (minimal server load)
- **Auto-refresh** - Dashboard updates every 5 seconds automatically
- **Responsive UI** - Clean, modern interface with gradient theme

## Architecture

```
┌──────────────────┐
│  FastAPI App     │
│  ┌────────────┐  │
│  │ Background │  │──RCON (every 10s)──> Minecraft Server
│  │  Polling   │  │                       (192.168.x.x:25575)
│  │   Task     │  │
│  └──────┬─────┘  │
│         ▼        │
│  ┌────────────┐  │
│  │   Cache    │  │
│  │  Service   │  │
│  └──────┬─────┘  │
│         ▼        │
│  ┌────────────┐  │
│  │    API     │◄─┼─── Dashboard (Browser)
│  │ Endpoints  │  │
│  └────────────┘  │
└──────────────────┘
```

**Benefits:**
- Only **6 RCON calls/min** regardless of how many users view the dashboard
- API responses return instantly from memory (<5ms) instead of waiting for RCON (50-200ms)
- Graceful degradation if Minecraft server goes offline

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Minecraft server with RCON enabled (see [RCON Setup Guide](RCON_SETUP.md))

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/anthonyi7/minecraft-dashboard.git
cd minecraft-dashboard
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure RCON connection**

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your Minecraft server details:
```bash
MC_SERVER_HOST=192.168.1.209    # Your server IP or hostname
MC_RCON_PORT=25575              # RCON port (default 25575)
MC_RCON_PASSWORD=your_password  # RCON password from server.properties
```

4. **Start the dashboard**
```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

5. **Open in browser**
```
http://localhost:8000
```

You should see:
```
Background polling task started - polling RCON every 10 seconds
Cache updated: Server online, 0/20 players
```

## Configuration

### Environment Variables

All configuration is done via `.env` file (git-ignored for security):

| Variable | Description | Default |
|----------|-------------|---------|
| `MC_SERVER_HOST` | Minecraft server IP or hostname | `localhost` |
| `MC_RCON_PORT` | RCON port number | `25575` |
| `MC_RCON_PASSWORD` | RCON password (must match server.properties) | *(required)* |

### Adjusting Poll Interval

Edit `app.py` line 91 to change background polling frequency:
```python
await asyncio.sleep(10)  # Change 10 to desired seconds
```

### Adjusting Staleness Threshold

Edit `cache_service.py` to change when data is considered stale:
```python
result["stale"] = age_seconds > 30  # Change 30 to desired seconds
```

## API Endpoints

### `GET /api/healthz`
Health check for the dashboard backend.

**Response:**
```json
{"ok": true}
```

### `GET /api/status`
Complete server status with players, performance, and metadata.

**Response:**
```json
{
  "online": true,
  "players": {
    "current": ["Steve", "Alex"],
    "count": 2,
    "max": 20
  },
  "performance": {
    "tps": 19.87,
    "memory_used_mb": 2048,
    "memory_total_mb": 4096
  },
  "stale": false,
  "last_updated": "2024-01-15T12:34:56Z",
  "last_error": null
}
```

### `GET /api/players`
Player information only.

**Response:**
```json
{
  "current": ["Steve", "Alex"],
  "count": 2,
  "max": 20,
  "stale": false,
  "last_updated": "2024-01-15T12:34:56Z"
}
```

## Project Structure

```
minecraft_dashboard/
├── app.py              # FastAPI application and background polling
├── cache_service.py    # In-memory cache for server data
├── rcon_service.py     # RCON communication with Minecraft server
├── config.py           # Environment variable configuration
├── requirements.txt    # Python dependencies
├── .env                # Local config (git-ignored, contains secrets)
├── .env.example        # Template for .env file
├── .gitignore          # Git ignore rules
├── RCON_SETUP.md       # Guide to enable RCON on Minecraft server
├── static/
│   ├── index.html      # Dashboard UI
│   ├── styles.css      # Styling
│   └── app.js          # Frontend JavaScript
└── README.md           # This file
```

## Troubleshooting

### "Connection refused" or "getaddrinfo failed"
- Verify Minecraft server IP is correct in `.env`
- Check that RCON is enabled in `server.properties`
- Ensure firewall allows connection on RCON port

### "Authentication failed"
- Password in `.env` must exactly match `rcon.password` in `server.properties`
- Restart Minecraft server after changing RCON settings

### Dashboard shows "stale: true"
- RCON polling is failing - check console logs for error messages
- Verify Minecraft server is online and reachable

### Performance metrics show mocked data
- TPS and memory metrics are currently mocked (planned for future update)
- Player data is real and accurate

## Roadmap

- [ ] Real TPS and memory metrics via RCON/SSH
- [ ] SQLite database for player session history
- [ ] Historical graphs and analytics
- [ ] Backup log monitoring
- [ ] Docker containerization
- [ ] Kubernetes deployment manifests
- [ ] Multi-server support

## Development

The server runs with auto-reload enabled. Any changes to Python files will automatically restart the backend.

**Start development server:**
```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

**Stop server:**
```
Ctrl+C
```

## Contributing

Feel free to open issues or submit pull requests!

## License

MIT

---

Built using FastAPI, RCON, and modern web technologies.
