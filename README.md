# Minecraft Dashboard

A real-time web dashboard for monitoring your Minecraft server with RCON integration, SSH-based performance metrics, and SQLite persistence for player session tracking.


**Disclaimer: Portions of this dashboard have been created using Claude. This project serves as an experiment for Claude integration with my knowledge of Python and containerized applications.**


![Status](https://img.shields.io/badge/status-active-success)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-green)

## Features

### Real-time Monitoring
- **Live Server Status** - Online/offline detection via RCON
- **Player Tracking** - Real-time player list and join/leave detection
- **Performance Metrics** - TPS, Memory, CPU, and Disk usage via SSH

### Background Polling & Caching
- **Efficient Polling** - Polls RCON and SSH every 5 seconds
- **Instant API Responses** - Sub-millisecond response times from in-memory cache
- **Resilient** - Shows last known good data if RCON/SSH temporarily fails
- **Scalable** - Multiple dashboards share the same cache (minimal server load)

### Player Session Tracking
- **SQLite Persistence** - Stores player join/leave events with session durations
- **Today's Activity** - View all players who joined today with total playtime
- **Historical Data** - Session data persists across dashboard restarts
- **Real-time Status** - Shows which players are currently online

### User Interface
- **Auto-refresh** - Dashboard updates every 5 seconds automatically
- **Responsive Design** - Clean, modern interface with gradient theme
- **Activity Table** - Sortable player activity with online status indicators

## Architecture

```
┌────────────────────────────────────────────────┐
│             FastAPI App                        │
│                                                │
│  ┌──────────────────────────────────────────┐ │
│  │       Background Polling Task            │ │
│  │      (every 5 seconds)                   │ │
│  └───┬──────────────────────────────┬───────┘ │
│      │                              │         │
│      ▼                              ▼         │
│  ┌─────────┐                   ┌─────────┐   │
│  │  RCON   │                   │   SSH   │   │──SSH──> Minecraft Server Host
│  │ Service │                   │ Service │   │          (192.168.x.x:22)
│  └────┬────┘                   └────┬────┘   │          - CPU usage
│       │                             │         │          - Memory usage
│       │    ┌────────────────┐       │         │          - Disk usage
│       └───>│  Cache Service │<──────┘         │          - TPS (if available)
│            └────────┬───────┘                 │
│                 │   │                         │
│      ┌──────────┘   └────────────┐            │
│      ▼                           ▼            │
│  ┌─────────┐              ┌────────────┐     │
│  │Database │              │    API     │◄────┼─── Dashboard (Browser)
│  │ Service │              │ Endpoints  │     │     - Server Status
│  │(SQLite) │              └────────────┘     │     - Player Activity
│  └─────────┘                                 │     - Performance Metrics
│      │                                       │
│      ▼                                       │
│  data/minecraft_dashboard.db                 │
│  (Player Sessions)                           │
└────────────────────────────────────────────────┘
        │
        │──RCON──> Minecraft Server
        │           (192.168.x.x:25575)
        │           - Online status
        │           - Player list
        │           - Max players
```

**Benefits:**
- Only **12 RCON calls/min** regardless of how many users view the dashboard
- API responses return instantly from memory (<5ms) instead of waiting for RCON/SSH (50-200ms)
- Graceful degradation if Minecraft server goes offline
- Player session data persists across restarts
- Real performance metrics from the host system (not mocked)

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

3. **Configure environment variables**

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your server details:
```bash
# Minecraft RCON Configuration
MC_SERVER_HOST=192.168.1.209           # Your server IP or hostname
MC_RCON_PORT=25575                     # RCON port (default 25575)
MC_RCON_PASSWORD=your_password         # RCON password from server.properties

# Database Configuration
DB_PATH=data/minecraft_dashboard.db    # SQLite database path

# SSH Configuration (for performance metrics)
SSH_HOST=192.168.1.209                 # SSH host (usually same as MC_SERVER_HOST)
SSH_PORT=22                            # SSH port (default 22)
SSH_USER=ubuntu                        # SSH username
SSH_KEY_PATH=~/.ssh/mc_dashboard_key   # Path to SSH private key
MC_SERVER_DIR=/home/ubuntu/minecraft   # Minecraft server directory on remote host
```

**Note:** For SSH metrics to work, you need to set up SSH key authentication:
```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/mc_dashboard_key -N ""

# Copy public key to Minecraft server
ssh-copy-id -i ~/.ssh/mc_dashboard_key.pub ubuntu@192.168.1.209

# Test the connection
ssh -i ~/.ssh/mc_dashboard_key ubuntu@192.168.1.209 "uptime"
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
Database initialized
No orphaned sessions found
Background polling task started - polling RCON every 5 seconds
Cache updated: Server online, 0/20 players
```

## Docker Deployment

The dashboard is containerized and available as a Docker image for easy deployment.

### Building Your Own Image

1. **Clone the repository**
```bash
git clone https://github.com/anthonyi7/minecraft-dashboard.git
cd minecraft-dashboard
```

2. **Build the Docker image**
```bash
docker build -t YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:latest .
```

3. **Push to DockerHub (optional)**
```bash
docker login
docker push YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:latest
```

## Kubernetes Deployment

For production deployments, Kubernetes provides orchestration, auto-restart, and persistent storage.

### Prerequisites

- Kubernetes cluster (GKE, EKS, AKS, or local k3s/minikube)
- `kubectl` configured to access your cluster
- SSH private key for accessing Minecraft server

### Quick Deploy with Kustomize

1. **Clone the repository**
```bash
git clone https://github.com/anthonyi7/minecraft-dashboard.git
cd minecraft-dashboard
```

2. **Edit configuration**

Update [k8s/configmap.yaml](k8s/configmap.yaml) with your server details:
```yaml
data:
  MC_SERVER_HOST: "192.168.1.209"  # Your Minecraft server IP
  MC_RCON_PORT: "25575"
  SSH_HOST: "192.168.1.209"
  SSH_USER: "ubuntu"
  MC_SERVER_DIR: "/home/ubuntu/minecraft"
```

Update [k8s/deployment.yaml](k8s/deployment.yaml) with your DockerHub image:
```yaml
image: YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:latest
```

3. **Create Kubernetes Secrets**

```bash
# Create SSH key secret from your private key file
kubectl create secret generic minecraft-dashboard-ssh-key \
  --from-file=mc_dashboard_key=$HOME/.ssh/mc_dashboard_key

# Create RCON password secret
kubectl create secret generic minecraft-dashboard-secret \
  --from-literal=MC_RCON_PASSWORD='your_rcon_password_here'
```

4. **Deploy to Kubernetes**

```bash
# Using kubectl apply
kubectl apply -f k8s/

# Or using Kustomize
kubectl apply -k k8s/
```

5. **Access the dashboard**

```bash
# Get the external IP (for LoadBalancer service)
kubectl get service minecraft-dashboard

# Or use port-forward for testing
kubectl port-forward service/minecraft-dashboard 8000:80
```

Then open http://localhost:8000 in your browser.

### Kubernetes Architecture

```
┌─────────────────────────────────────────────┐
│          Kubernetes Cluster                 │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │   Service (LoadBalancer)              │ │
│  │   External IP: x.x.x.x:80             │ │
│  └──────────────┬────────────────────────┘ │
│                 │                           │
│  ┌──────────────▼────────────────────────┐ │
│  │   Deployment (1 replica)              │ │
│  │   - FastAPI container                 │ │
│  │   - Resource limits: 512Mi / 500m CPU │ │
│  │   - Health checks: /api/healthz       │ │
│  └──┬────────────────────────────────┬───┘ │
│     │                                │     │
│  ┌──▼──────────────┐     ┌───────────▼──┐ │
│  │ PVC (1Gi)       │     │ Secrets      │ │
│  │ SQLite database │     │ - SSH key    │ │
│  │ ReadWriteOnce   │     │ - RCON pass  │ │
│  └─────────────────┘     └──────────────┘ │
└─────────────────────────────────────────────┘
```

### Kubernetes Files Reference

| File | Description |
|------|-------------|
| [k8s/deployment.yaml](k8s/deployment.yaml) | Main application deployment with resource limits and health checks |
| [k8s/service.yaml](k8s/service.yaml) | LoadBalancer service exposing the dashboard on port 80 |
| [k8s/pvc.yaml](k8s/pvc.yaml) | PersistentVolumeClaim for SQLite database (1Gi) |
| [k8s/configmap.yaml](k8s/configmap.yaml) | Non-sensitive environment variables |
| [k8s/secrets-example.yaml](k8s/secrets-example.yaml) | Template for creating secrets (DO NOT commit with real values!) |
| [k8s/kustomization.yaml](k8s/kustomization.yaml) | Kustomize configuration for easy manifest management |

### Production Best Practices

**Security:**
 SSH key mounted from Kubernetes Secret (never baked into image)
RCON password stored in Secret (not ConfigMap)
Container runs as non-root user (UID 1000)
 Security context with dropped capabilities
Consider using [sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) or [external-secrets](https://external-secrets.io/) for production

**Persistence:**
SQLite database on PersistentVolume (survives pod restarts)
 Backup PVC regularly (SQLite database contains all session history)
Consider using a managed database (PostgreSQL) for multi-replica deployments

**Monitoring:**
Health checks configured (liveness and readiness probes)
Add Prometheus metrics for production monitoring
Set up alerts for pod restarts or health check failures

**Scaling:**
SQLite limitation: Cannot scale beyond 1 replica (ReadWriteOnce PVC)
For high availability, migrate to PostgreSQL or MySQL and use ReadWriteMany storage

### Updating the Deployment

```bash
# Build and push new image
docker build -t YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:v1.0.1 .
docker push YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:v1.0.1

# Update deployment
kubectl set image deployment/minecraft-dashboard \
  dashboard=YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:v1.0.1

# Or edit kustomization.yaml and reapply
kubectl apply -k k8s/
```



## Configuration

### Environment Variables

All configuration is done via `.env` file (git-ignored for security):

#### RCON Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `MC_SERVER_HOST` | Minecraft server IP or hostname | `localhost` |
| `MC_RCON_PORT` | RCON port number | `25575` |
| `MC_RCON_PASSWORD` | RCON password (must match server.properties) | *(required)* |

#### Database Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `DB_PATH` | Path to SQLite database file | `data/minecraft_dashboard.db` |

#### SSH Configuration (for Performance Metrics)
| Variable | Description | Default |
|----------|-------------|---------|
| `SSH_HOST` | SSH host for metrics collection | `localhost` |
| `SSH_PORT` | SSH port | `22` |
| `SSH_USER` | SSH username | `ubuntu` |
| `SSH_KEY_PATH` | Path to SSH private key (supports `~` expansion) | `~/.ssh/mc_dashboard_key` |
| `MC_SERVER_DIR` | Minecraft server directory on remote host | `/home/ubuntu/minecraft` |

### Adjusting Poll Interval

Edit the sleep interval in [app.py](app.py) background polling loop:
```python
await asyncio.sleep(5)  # Change 5 to desired seconds (line ~125)
```

**Note:** Lower intervals increase RCON/SSH load. Recommended range: 5-30 seconds.

### Adjusting Staleness Threshold

Edit [cache_service.py](cache_service.py) to change when data is considered stale:
```python
result["stale"] = age_seconds > 30  # Change 30 to desired seconds (line ~117)
```

## API Endpoints

### `GET /api/healthz`
Health check for the dashboard backend.

**Response:**
```json
{"ok": true}
```

### `GET /api/status`
Complete server status with players, performance metrics, and metadata.

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
    "memory_used_mb": 4096,
    "memory_total_mb": 8192,
    "cpu_percent": 45.2,
    "disk_used_gb": 15.3,
    "disk_total_gb": 50.0
  },
  "stale": false,
  "last_updated": "2024-01-15T12:34:56Z",
  "last_error": null
}
```

**Performance Metrics Explained:**
- `tps`: Server ticks per second (20.0 = perfect, <19.0 = lag)
- `memory_used_mb` / `memory_total_mb`: Java process memory usage
- `cpu_percent`: CPU usage of Minecraft process (0-100% per core)
- `disk_used_gb` / `disk_total_gb`: Disk usage of server directory

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

### `GET /api/today`
Player activity statistics for today (midnight Pacific to now).

**Response:**
```json
{
  "date": "2024-02-15",
  "timezone": "America/Los_Angeles (Pacific)",
  "players": [
    {
      "name": "Steve",
      "total_playtime_seconds": 7200,
      "total_playtime_formatted": "2h 0m",
      "session_count": 3,
      "currently_online": false
    },
    {
      "name": "Alex",
      "total_playtime_seconds": 3600,
      "total_playtime_formatted": "1h 0m",
      "session_count": 1,
      "currently_online": true
    }
  ],
  "summary": {
    "unique_players": 2,
    "total_playtime_seconds": 10800,
    "total_sessions": 4
  }
}
```

**Notes:**
- "Today" is calculated based on Pacific time (midnight to now)
- `currently_online` reflects real-time RCON data
- Active sessions (players still online) are included with current duration
- Data persists across dashboard restarts via SQLite

## Project Structure

```
minecraft_dashboard/
├── app.py              # FastAPI application and background polling
├── cache_service.py    # In-memory cache for server data
├── rcon_service.py     # RCON communication with Minecraft server
├── db_service.py       # SQLite database for player session tracking
├── ssh_service.py      # SSH-based performance metrics collection
├── stats_service.py    # Minecraft statistics collection (blocks, distance, playtime)
├── config.py           # Environment variable configuration
├── requirements.txt    # Python dependencies (FastAPI, mcrcon, paramiko, etc.)
├── .env                # Local config (git-ignored, contains secrets)
├── .env.example        # Template for .env file
├── .gitignore          # Git ignore rules
├── RCON_SETUP.md       # Guide to enable RCON on Minecraft server
├── Dockerfile          # Multi-stage Docker build configuration
├── .dockerignore       # Files to exclude from Docker build context
├── data/               # Auto-created directory for database (git-ignored)
│   └── minecraft_dashboard.db  # SQLite database (player sessions)
├── k8s/                # Kubernetes manifests
│   ├── deployment.yaml      # K8s Deployment with health checks and resource limits
│   ├── service.yaml         # K8s Service (LoadBalancer)
│   ├── pvc.yaml             # PersistentVolumeClaim for SQLite database
│   ├── configmap.yaml       # Non-sensitive environment variables
│   ├── secrets-example.yaml # Template for creating Secrets (git-ignored)
│   └── kustomization.yaml   # Kustomize configuration
├── static/
│   ├── index.html      # Dashboard UI (server status, player activity table, leaderboards)
│   ├── styles.css      # Styling (gradient theme, responsive tables)
│   └── app.js          # Frontend JavaScript (API polling, UI updates)
└── README.md           # This file
```



## Database Schema

The SQLite database uses a single table for player session tracking:

```sql
CREATE TABLE player_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    joined_at TIMESTAMP NOT NULL,      -- UTC timestamp when player joined
    left_at TIMESTAMP DEFAULT NULL,    -- NULL = currently online
    duration_seconds INTEGER DEFAULT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Session Tracking Logic:**
1. Background polling compares current player list with previous poll
2. New players trigger `INSERT` with `left_at=NULL` (indicates online)
3. Players who left trigger `UPDATE` to set `left_at` and compute `duration_seconds`
4. On startup, orphaned sessions (left_at=NULL from crashes) are closed with 0 duration

**Example Query (Today's Activity):**
```sql
SELECT
    player_name,
    COUNT(*) as session_count,
    SUM(CASE
        WHEN left_at IS NULL THEN (strftime('%s', 'now') - strftime('%s', joined_at))
        ELSE duration_seconds
    END) as total_playtime_seconds
FROM player_sessions
WHERE joined_at >= datetime('now', 'start of day', '-8 hours')  -- Pacific time
GROUP BY player_name
ORDER BY total_playtime_seconds DESC;
```

## Performance Metrics via SSH

The dashboard collects real performance metrics from the Minecraft server host via SSH:

| Metric | SSH Command | Description |
|--------|-------------|-------------|
| **CPU** | `ps -p {pid} -o %cpu` | CPU usage of Java/Minecraft process |
| **Memory** | `ps -p {pid} -o rss` | RSS memory usage in MB |
| **Disk** | `df -BG {server_dir}` | Disk usage of server directory |
| **TPS** | `tail -100 logs/latest.log \| grep -i tps` | Server TPS (if logged by mods) |

**Process Discovery:**
- Finds Minecraft PID: `pgrep -f 'java.*minecraft|java.*forge|java.*neoforge'`
- Caches PID to reduce SSH overhead
- Falls back to safe values (0.0, 20.0 TPS) on SSH failure

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

**View database contents:**
```bash
sqlite3 data/minecraft_dashboard.db "SELECT * FROM player_sessions ORDER BY joined_at DESC LIMIT 10;"
```

**Clear database (fresh start):**
```bash
rm data/minecraft_dashboard.db
# Database will be recreated on next app start
```

## Contributing

Feel free to open issues or submit pull requests!

## License

MIT

---

Built using FastAPI, RCON, and modern web technologies.

