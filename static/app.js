const API_BASE = '/api';

async function fetchStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const data = await response.json();

        updateUI(data);
        updateTimestamp();
    } catch (error) {
        console.error('Failed to fetch status:', error);
        showError();
    }
}

function updateUI(data) {
    // Update server status
    const statusEl = document.getElementById('server-status');
    statusEl.textContent = data.online ? 'Online' : 'Offline';
    statusEl.className = data.online ? 'status status-online' : 'status status-offline';

    // Update player count and list
    document.getElementById('player-count').textContent =
        `${data.players.count} / ${data.players.max} players`;

    const playerList = document.getElementById('player-list');
    playerList.innerHTML = '';
    data.players.current.forEach(player => {
        const li = document.createElement('li');
        li.textContent = player;
        playerList.appendChild(li);
    });

    // Update performance metrics
    document.getElementById('tps').textContent = data.performance.tps.toFixed(2);
    document.getElementById('memory').textContent =
        `${data.performance.memory_used_mb} / ${data.performance.memory_total_mb} MB`;
}

function updateTimestamp() {
    const now = new Date().toLocaleTimeString();
    document.getElementById('last-updated').textContent = now;
}

function showError() {
    document.getElementById('server-status').textContent = 'Error';
    document.getElementById('server-status').className = 'status status-offline';
}

// Fetch on page load
fetchStatus();

// Auto-refresh every 5 seconds
setInterval(fetchStatus, 5000);
