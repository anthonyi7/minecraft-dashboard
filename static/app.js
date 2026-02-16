const API_BASE = '/api';

// Store current online players for real-time status updates
let currentOnlinePlayers = new Set();

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

async function fetchTodayStats() {
    try {
        const response = await fetch(`${API_BASE}/today`);
        const data = await response.json();

        updateTodayUI(data);
    } catch (error) {
        console.error('Failed to fetch today stats:', error);
        showTodayError();
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
    document.getElementById('cpu').textContent = `${data.performance.cpu_percent.toFixed(1)}%`;
    document.getElementById('disk').textContent =
        `${data.performance.disk_used_gb.toFixed(1)} / ${data.performance.disk_total_gb.toFixed(1)} GB`;

    // Store current online players for use in Today's Activity table
    currentOnlinePlayers = new Set(data.players.current);
}

function updateTimestamp() {
    const now = new Date().toLocaleTimeString();
    document.getElementById('last-updated').textContent = now;
}

function updateTodayUI(data) {
    // Update summary
    const summaryEl = document.getElementById('today-summary');
    summaryEl.textContent = `${data.summary.unique_players} players seen today • ${formatTotalTime(data.summary.total_playtime_seconds)} total playtime • ${data.summary.total_sessions} sessions`;
    summaryEl.className = 'today-summary';

    // Update table
    const tbody = document.getElementById('player-activity-body');
    tbody.innerHTML = '';

    if (data.players.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="3" class="no-data">No player activity today</td>';
        tbody.appendChild(row);
        return;
    }

    data.players.forEach(player => {
        const row = document.createElement('tr');

        // Player name cell
        const nameCell = document.createElement('td');
        nameCell.textContent = player.name;
        nameCell.className = 'player-name';
        row.appendChild(nameCell);

        // Playtime cell
        const timeCell = document.createElement('td');
        timeCell.textContent = player.total_playtime_formatted;
        timeCell.className = 'playtime';
        row.appendChild(timeCell);

        // Status cell with online indicator - USE LIVE RCON DATA
        const statusCell = document.createElement('td');
        const indicator = document.createElement('span');
        const isOnline = currentOnlinePlayers.has(player.name);  // Check live RCON data
        indicator.className = isOnline ? 'status-indicator online' : 'status-indicator offline';
        indicator.textContent = isOnline ? 'Online' : 'Offline';
        statusCell.appendChild(indicator);
        row.appendChild(statusCell);

        tbody.appendChild(row);
    });
}

function formatTotalTime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    const remainingMinutes = minutes % 60;
    return remainingMinutes === 0 ? `${hours}h` : `${hours}h ${remainingMinutes}m`;
}

function showError() {
    document.getElementById('server-status').textContent = 'Error';
    document.getElementById('server-status').className = 'status status-offline';
}

function showTodayError() {
    const tbody = document.getElementById('player-activity-body');
    tbody.innerHTML = '<tr><td colspan="3" class="error">Failed to load player activity</td></tr>';
}

async function fetchLeaderboards() {
    try {
        const response = await fetch(`${API_BASE}/leaderboards`);
        const data = await response.json();
        updateLeaderboards(data);
    } catch (error) {
        console.error('Failed to fetch leaderboards:', error);
        showLeaderboardError();
    }
}

function updateLeaderboards(data) {
    updateLeaderboardTable('playtime-leaderboard', data.playtime);
    updateLeaderboardTable('blocks-leaderboard', data.blocks);
    updateLeaderboardTable('distance-leaderboard', data.distance);
}

function updateLeaderboardTable(tableBodyId, players) {
    const tbody = document.getElementById(tableBodyId);
    tbody.innerHTML = '';

    if (!players || players.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-data">No data available</td></tr>';
        return;
    }

    players.forEach((player, index) => {
        const row = document.createElement('tr');

        // Rank
        const rankCell = document.createElement('td');
        rankCell.textContent = index + 1;
        rankCell.className = 'rank';
        row.appendChild(rankCell);

        // Player name
        const nameCell = document.createElement('td');
        nameCell.textContent = player.name;
        nameCell.className = 'player-name';
        row.appendChild(nameCell);

        // Value (formatted)
        const valueCell = document.createElement('td');
        valueCell.textContent = player.formatted;
        valueCell.className = 'leaderboard-value';
        row.appendChild(valueCell);

        tbody.appendChild(row);
    });
}

function showLeaderboardError() {
    ['playtime-leaderboard', 'blocks-leaderboard', 'distance-leaderboard'].forEach(id => {
        const tbody = document.getElementById(id);
        tbody.innerHTML = '<tr><td colspan="3" class="error">Failed to load</td></tr>';
    });
}

// Fetch on page load
fetchStatus();
fetchTodayStats();
fetchLeaderboards();

// Auto-refresh every 5 seconds
setInterval(fetchStatus, 5000);
setInterval(fetchTodayStats, 5000);
setInterval(fetchLeaderboards, 5000);
