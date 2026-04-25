# Minecraft Dashboard

A web dashboard for monitoring your Minecraft server with RCON integration, SSH-based performance metrics, and SQLite persistence for player session tracking.


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

### Player Session Tracking
- **SQLite Persistence** - Stores player join/leave events with session durations
- **Today's Activity** - View all players who joined today with total playtime
- **Yesterday's Activity** - Previous day's session summary
- **Historical Data** - Session data persists across dashboard restarts

### User Interface
- **Auto-refresh** - Dashboard updates every 5 seconds automatically
- **Responsive Design** - Clean, modern interface with gradient theme
- **Leaderboards** - Total Playtime, Blocks Destroyed, Distance Traveled

## Architecture

The dashboard is split into two tiers to avoid exposing RCON/SSH credentials publicly.

```
┌──────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  secure-minecraft-dashboard (FastAPI, internal only)   │  │
│  │                                                        │  │
│  │  ┌─────────────┐   ┌─────────────┐   ┌────────────┐  │  │
│  │  │ RCON Service│   │ SSH Service │   │  DB Service│  │  │
│  │  └──────┬──────┘   └──────┬──────┘   └─────┬──────┘  │  │
│  │         └────────────┬────┘                │          │  │
│  │                      ▼                     ▼          │  │
│  │               ┌─────────────┐      ┌──────────────┐  │  │
│  │               │    Cache    │      │   SQLite PVC │  │  │
│  │               └──────┬──────┘      └──────────────┘  │  │
│  │                      │  /api/*                        │  │
│  └──────────────────────┼────────────────────────────────┘  │
│                         │                                    │
│  ┌──────────────────────▼──────┐   ┌──────────────────────┐ │
│  │  snapshot-writer (CronJob)  │   │  db-backup (CronJob) │ │
│  │  runs every 1 minute        │   │  runs daily at 3 AM  │ │
│  │  writes snapshot.json → PVC │   │  SCPs db → MC server │ │
│  └──────────────────────┬──────┘   └──────────────────────┘ │
│                         │                                    │
│  ┌──────────────────────▼────────────────────────────────┐  │
│  │  minecraft-dashboard (nginx, public)                   │  │
│  │  serves index.html + snapshot.json from PVC            │  │
│  └──────────────────────┬──────────────────────────────── ┘  │
│                         │                                    │
│  ┌──────────────────────▼──────────────┐                    │
│  │  Ingress (ingress-nginx + MetalLB)  │                    │
│  │  status.mff-server.com (HTTPS)      │                    │
│  └─────────────────────────────────────┘                    │
└──────────────────────────────────────────────────────────────┘
         │ RCON (port 25576)           │ SSH (port 22)
         ▼                             ▼
   Minecraft Server (192.168.1.x)
```

**Why two tiers?**
- The secure backend is cluster-internal only — RCON and SSH credentials never leave the cluster
- The public nginx pod serves a static snapshot refreshed every minute — safe to expose without auth
- Only 12 RCON calls/min regardless of how many users view the dashboard

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
MC_SERVER_HOST=192.168.1.x             # Your Minecraft server IP
MC_RCON_PORT=25576                     # RCON port (check your server.properties)
MC_RCON_PASSWORD=your_password         # RCON password from server.properties

# Database Configuration
DB_PATH=data/minecraft_dashboard.db    # SQLite database path

# SSH Configuration (for performance metrics)
SSH_HOST=192.168.1.x                   # SSH host (usually same as MC_SERVER_HOST)
SSH_PORT=22                            # SSH port (default 22)
SSH_USER=ubuntu                        # SSH username
SSH_KEY_PATH=~/.ssh/mc_dashboard_key   # Path to SSH private key
MC_SERVER_DIR=/mnt/storage/minecraft   # Minecraft server directory on remote host
```

**Note:** For SSH metrics to work, set up SSH key authentication:
```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/mc_dashboard_key -N ""

# Copy public key to Minecraft server
ssh-copy-id -i ~/.ssh/mc_dashboard_key.pub ubuntu@192.168.1.x

# Test the connection
ssh -i ~/.ssh/mc_dashboard_key ubuntu@192.168.1.x "uptime"
```

4. **Start the dashboard**
```bash
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

5. **Open in browser**
```
http://localhost:8000
```

## Docker Deployment

```bash
docker run -d \
  --name minecraft-dashboard \
  -p 8000:8000 \
  -v $(pwd)/data:/app/data \
  -v ~/.ssh/mc_dashboard_key:/home/appuser/.ssh/mc_dashboard_key:ro \
  -e MC_SERVER_HOST=192.168.1.x \
  -e MC_RCON_PORT=25576 \
  -e MC_RCON_PASSWORD=your_password \
  -e SSH_HOST=192.168.1.x \
  -e SSH_USER=ubuntu \
  -e MC_SERVER_DIR=/mnt/storage/minecraft \
  fullstackant/minecraft-dashboard:latest
```

### Building Your Own Image

```bash
docker build -t YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:latest .
docker push YOUR_DOCKERHUB_USERNAME/minecraft-dashboard:latest
```

The public nginx image (for the static snapshot tier) is built separately:
```bash
docker build -f Dockerfile.public -t YOUR_DOCKERHUB_USERNAME/minecraft-dashboard-public:latest .
docker push YOUR_DOCKERHUB_USERNAME/minecraft-dashboard-public:latest
```

## Kubernetes Deployment

### Prerequisites

- Kubernetes cluster with:
  - [Longhorn](https://longhorn.io/) for persistent storage (replicated across nodes)
  - [MetalLB](https://metallb.universe.tf/) for LoadBalancer IPs (bare-metal)
  - [ingress-nginx](https://kubernetes.github.io/ingress-nginx/) (community Helm chart — `kubernetes.github.io/ingress-nginx`, **not** `helm.nginx.com`)
  - [cert-manager](https://cert-manager.io/) for automatic TLS certificates
- `kubectl` configured to access your cluster
- SSH private key for accessing Minecraft server

### Deploy

1. **Create the namespace**
```bash
kubectl create namespace mff
```

2. **Create secrets**
```bash
# SSH key for metrics collection
kubectl create secret generic minecraft-dashboard-ssh-key \
  --from-file=mc_dashboard_key=$HOME/.ssh/mc_dashboard_key \
  -n mff

# RCON password
kubectl create secret generic minecraft-dashboard-secret \
  --from-literal=MC_RCON_PASSWORD='your_rcon_password' \
  -n mff
```

3. **Update configuration**

Edit [k8s/configmap.yaml](k8s/configmap.yaml) with your server details:
```yaml
data:
  MC_SERVER_HOST: "192.168.1.x"
  MC_RCON_PORT: "25576"
  SSH_HOST: "192.168.1.x"
  SSH_USER: "ubuntu"
  MC_SERVER_DIR: "/mnt/storage/minecraft"
```

Update the `nodeSelector` in [k8s/deployment.yaml](k8s/deployment.yaml) and [k8s/public-deployment.yaml](k8s/public-deployment.yaml) to pin both pods to the same worker node (required because Longhorn RWO volumes attach to one node at a time):
```yaml
nodeSelector:
  kubernetes.io/hostname: worker1  # change to your target node
```

4. **Deploy with Kustomize**
```bash
kubectl apply -k k8s/
```

5. **Set PV reclaim policy to Retain**

After the PVC is created, patch the backing PV so it survives namespace deletion:
```bash
PV=$(kubectl get pvc minecraft-dashboard-data -n mff -o jsonpath='{.spec.volumeName}')
kubectl patch pv $PV -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

### Kubernetes Architecture

```
Namespace: mff
├── secure-minecraft-dashboard    Deployment (1 replica, pinned to worker1)
│   ├── PVC: minecraft-dashboard-data (1Gi, Longhorn, ReclaimPolicy: Retain)
│   └── Secret: minecraft-dashboard-ssh-key
│
├── minecraft-dashboard           Deployment (1 replica, pinned to worker1)
│   └── PVC: snapshot-data (50Mi, Longhorn) — read-only mount
│
├── snapshot-writer               CronJob (every 1 min)
│   └── Fetches /api/* from secure backend → writes snapshot.json to snapshot-data PVC
│
├── db-backup                     CronJob (daily at 3 AM)
│   └── Copies SQLite db → ubuntu@192.168.1.x:/home/ubuntu/mc_dashboard_backups/
│       Keeps last 7 daily backups
│
└── minecraft-dashboard           Ingress
    └── status.mff-server.com → minecraft-dashboard:80 (TLS via cert-manager)
```

### Kubernetes Files Reference

| File | Description |
|------|-------------|
| [k8s/deployment.yaml](k8s/deployment.yaml) | Secure FastAPI backend — RCON/SSH, SQLite, internal only |
| [k8s/service.yaml](k8s/service.yaml) | ClusterIP service for secure backend (port 8000) |
| [k8s/pvc.yaml](k8s/pvc.yaml) | PVC for SQLite database (1Gi, Longhorn) |
| [k8s/public-deployment.yaml](k8s/public-deployment.yaml) | Public nginx — serves index.html + snapshot.json |
| [k8s/public-service.yaml](k8s/public-service.yaml) | ClusterIP service for public nginx (port 80) |
| [k8s/snapshot-pvc.yaml](k8s/snapshot-pvc.yaml) | PVC for snapshot.json shared between cronjob and public nginx (50Mi) |
| [k8s/snapshot-cronjob.yaml](k8s/snapshot-cronjob.yaml) | Cronjob that polls the secure backend and writes snapshot.json every minute |
| [k8s/db-backup-cronjob.yaml](k8s/db-backup-cronjob.yaml) | Daily cronjob that SCPs the SQLite db to the Minecraft server (7-day retention) |
| [k8s/ingress-status.yaml](k8s/ingress-status.yaml) | Ingress for status.mff-server.com with TLS via cert-manager |
| [k8s/configmap.yaml](k8s/configmap.yaml) | Non-sensitive environment variables (server IPs, ports, paths) |
| [k8s/secrets-example.yaml](k8s/secrets-example.yaml) | Template for creating secrets (do not commit with real values) |
| [k8s/kustomization.yaml](k8s/kustomization.yaml) | Kustomize config — applies all manifests to namespace `mff` |

<<<<<<< HEAD
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
=======
### Data Protection
>>>>>>> 3f1511e (Update for k8s manifests, data protection, TLS, backups, and more)

**Reclaim policy: Retain**
The SQLite PVC's backing PV is patched to `Retain`. If the namespace or PVC is deleted, the Longhorn volume is preserved (status goes to `Released`). To reattach after rebuilding:
```bash
# Find the released PV
kubectl get pv | grep Released

# Remove the old claimRef so it can be rebound
kubectl patch pv <pv-name> --type=json \
  -p='[{"op":"remove","path":"/spec/claimRef"}]'

# Recreate the PVC — it will bind to the existing PV
kubectl apply -k k8s/
```

<<<<<<< HEAD

=======
**Daily off-cluster backup**
The `db-backup` CronJob runs at 3 AM and SCPs the database to `/home/ubuntu/mc_dashboard_backups/` on the Minecraft server, keeping the last 7 daily files.

To restore from backup:
```bash
# Copy backup from Minecraft server to local machine
scp ubuntu@192.168.1.x:/home/ubuntu/mc_dashboard_backups/minecraft_dashboard_YYYYMMDD.db ./restore.db

# Copy into the running pod
POD=$(kubectl get pod -n mff -l app=secure-minecraft-dashboard -o jsonpath='{.items[0].metadata.name}')
kubectl cp restore.db mff/$POD:/app/data/minecraft_dashboard.db

# Restart the pod to reinitialize
kubectl rollout restart deployment/secure-minecraft-dashboard -n mff
```

To trigger a manual backup immediately:
```bash
kubectl create job --from=cronjob/db-backup db-backup-manual -n mff
kubectl logs -n mff -l job-name=db-backup-manual
```

### Ingress & TLS Notes

This setup uses the **community ingress-nginx controller** (`kubernetes.github.io/ingress-nginx` Helm chart). The NGINX Inc. controller (`helm.nginx.com`) is **not compatible** with cert-manager's HTTP01 solver — it rejects multiple ingresses sharing a hostname, which blocks ACME challenge validation.

Install the correct controller:
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx --create-namespace
```

### Troubleshooting Kubernetes

```bash
# Check pod status
kubectl get pods -n mff

# Secure backend logs (RCON/SSH errors will appear here)
kubectl logs -n mff -l app=secure-minecraft-dashboard --tail=50

# Public nginx logs
kubectl logs -n mff -l app=minecraft-dashboard --tail=50

# Check snapshot cronjob last run
kubectl get jobs -n mff

# Check certificate status
kubectl get certificate -n mff
kubectl describe certificate status-mff-server-tls -n mff

# Check ingress
kubectl get ingress -n mff
kubectl describe ingress minecraft-dashboard -n mff

# Verify configmap values are correct
kubectl get configmap minecraft-dashboard-config -n mff -o yaml

# Port-forward to inspect the secure backend API directly
kubectl port-forward svc/secure-minecraft-dashboard -n mff 8000:8000
# then visit: http://localhost:8000/api/status
```
>>>>>>> 3f1511e (Update for k8s manifests, data protection, TLS, backups, and more)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MC_SERVER_HOST` | Minecraft server IP or hostname | `localhost` |
| `MC_RCON_PORT` | RCON port number | `25576` |
| `MC_RCON_PASSWORD` | RCON password (must match server.properties) | *(required)* |
| `DB_PATH` | Path to SQLite database file | `data/minecraft_dashboard.db` |
| `SSH_HOST` | SSH host for metrics collection | `localhost` |
| `SSH_PORT` | SSH port | `22` |
| `SSH_USER` | SSH username | `ubuntu` |
| `SSH_KEY_PATH` | Path to SSH private key | `~/.ssh/mc_dashboard_key` |
| `MC_SERVER_DIR` | Minecraft server directory on remote host | `/mnt/storage/minecraft` |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/healthz` | Health check — returns `{"ok": true}` |
| `GET /api/status` | Live server status, player list, performance metrics |
| `GET /api/today` | Player activity for today (midnight Pacific to now) |
| `GET /api/yesterday` | Player activity for yesterday (Pacific time) |
| `GET /api/leaderboards` | Total playtime, blocks destroyed, distance traveled |

## Project Structure

```
minecraft_dashboard/
├── app.py                  # FastAPI app and background polling
├── cache_service.py        # In-memory cache for server data
├── rcon_service.py         # RCON communication with Minecraft server
├── db_service.py           # SQLite for player session tracking
├── ssh_service.py          # SSH-based performance metrics
├── stats_service.py        # Minecraft stats files (blocks, distance, playtime)
├── config.py               # Environment variable configuration
├── requirements.txt        # Python dependencies
├── Dockerfile              # Secure backend image (FastAPI)
├── Dockerfile.public       # Public image (nginx serving static snapshot)
├── .env                    # Local config (git-ignored)
├── .env.example            # Template for .env
├── seed_db.py              # One-time script to seed SQLite from known player totals
├── public/
│   ├── index.html          # Dashboard UI (reads from /snapshot.json)
│   └── nginx.conf          # Nginx config for public container
├── k8s/                    # Kubernetes manifests (see table above)
├── data/                   # Auto-created; holds minecraft_dashboard.db (git-ignored)
├── RCON_SETUP.md           # Guide to enable RCON on Minecraft server
└── README.md               # This file
```


<<<<<<< HEAD
=======
### Dashboard shows server as "Offline"

Check the secure backend logs first:
```bash
kubectl logs -n mff -l app=secure-minecraft-dashboard --tail=30
```

Common causes:
- `No route to host` — wrong IP in configmap. Verify `MC_SERVER_HOST` and `SSH_HOST`.
- `Login failed` — wrong RCON password in secret. Re-create: `kubectl create secret generic minecraft-dashboard-secret --from-literal=MC_RCON_PASSWORD='correct_password' -n mff --dry-run=client -o yaml | kubectl replace -f -`, then restart the pod.
- After any configmap/secret change, restart: `kubectl rollout restart deployment/secure-minecraft-dashboard -n mff`

### Public page shows no data / "No activity"

The public page reads from `snapshot.json` on the shared PVC, written by the snapshot cronjob every minute. Check the cronjob:
```bash
kubectl get jobs -n mff | grep snapshot
kubectl logs -n mff -l job-name=<latest-snapshot-job>
```
If the secure backend is offline, the cronjob will skip writing. Fix the backend first.

### Certificate not issuing

Ensure you are using the community ingress-nginx controller (see Ingress & TLS Notes above). The NGINX Inc. controller is incompatible with cert-manager HTTP01 challenges.

### SSH Issues

```bash
# Missing key secret
kubectl get secret minecraft-dashboard-ssh-key -n mff

# Regenerate and recreate if missing
ssh-keygen -t rsa -b 4096 -f ~/.ssh/mc_dashboard_key -N ""
ssh-copy-id -i ~/.ssh/mc_dashboard_key.pub ubuntu@192.168.1.x
kubectl create secret generic minecraft-dashboard-ssh-key \
  --from-file=mc_dashboard_key=$HOME/.ssh/mc_dashboard_key -n mff
```
>>>>>>> 3f1511e (Update for k8s manifests, data protection, TLS, backups, and more)

## Database Schema

```sql
CREATE TABLE player_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name TEXT NOT NULL,
    event_type TEXT NOT NULL,          -- 'join' or 'leave'
    timestamp TIMESTAMP NOT NULL,      -- UTC
    session_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Today/Yesterday activity is derived at query time by summing join→leave pairs within the Pacific time day boundary.

## Roadmap

### Completed
- [x] Real TPS, Memory, CPU, and Disk metrics via SSH
- [x] SQLite player session tracking with today/yesterday panels
- [x] Leaderboards from Minecraft stats files (playtime, blocks, distance)
- [x] Docker containerization (secure backend + public nginx images)
- [x] Kubernetes deployment with two-tier architecture
- [x] Ingress with TLS via cert-manager (Let's Encrypt)
- [x] Longhorn PVC with Retain policy for data safety
- [x] Daily off-cluster SQLite backup to Minecraft server

### Planned
- [ ] PostgreSQL support for multi-replica deployments
- [ ] Prometheus metrics endpoint
- [ ] Helm chart

## License

MIT

---

<<<<<<< HEAD
Built using FastAPI, RCON, and modern web technologies.

=======
Built with FastAPI, RCON, and nginx.
>>>>>>> 3f1511e (Update for k8s manifests, data protection, TLS, backups, and more)
