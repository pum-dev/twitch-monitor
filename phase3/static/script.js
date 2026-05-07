const API_BASE = "/api";

async function fetchChannels() {
    try {
        const response = await fetch(`${API_BASE}/channels`);
        const channels = await response.json();
        updateChannelsTable(channels);
    } catch (error) {
        console.error("Error fetching channels:", error);
    }
}

async function fetchEvents() {
    try {
        const response = await fetch(`${API_BASE}/events`);
        const events = await response.json();
        updateEventsPanel(events);
    } catch (error) {
        console.error("Error fetching events:", error);
    }
}

async function fetchStatus() {
    try {
        const response = await fetch(`${API_BASE}/status`);
        const status = await response.json();
        updateStatusBar(status);
    } catch (error) {
        console.error("Error fetching status:", error);
    }
}

function updateChannelsTable(channels) {
    const tbody = document.getElementById("table-body");
    
    if (channels.length === 0) {
        tbody.innerHTML = "<tr><td colspan='7'>No hay canales monitoreados</td></tr>";
        return;
    }

    tbody.innerHTML = channels.map(ch => `
        <tr>
            <td><strong>${ch.name}</strong></td>
            <td>
                <span class="status-${ch.status.toLowerCase()}">
                    ${ch.status}
                </span>
            </td>
            <td>${ch.bitrate !== null ? ch.bitrate.toFixed(2) : "N/A"}</td>
            <td>${ch.fps !== null ? ch.fps.toFixed(2) : "N/A"}</td>
            <td>${ch.av_sync !== null ? (ch.av_sync * 1000).toFixed(0) : "N/A"}</td>
            <td>${ch.last_update ? new Date(ch.last_update).toLocaleTimeString() : "N/A"}</td>
            <td>
                <button class="btn-remove" onclick="removeChannel('${ch.name}')">
                    Remover
                </button>
            </td>
        </tr>
    `).join("");
}

function updateEventsPanel(events) {
    const container = document.getElementById("events-container");
    
    if (events.length === 0) {
        container.innerHTML = "<p>No hay eventos recientes</p>";
        return;
    }

    container.innerHTML = events.map(event => {
        const severity = event.severity.toLowerCase();
        return `
            <div class="event-item event-${severity}">
                <strong>${event.channel}</strong> - ${event.type}
                <div class="event-info">
                    ${event.message}<br>
                    <span>${new Date(event.timestamp).toLocaleString()}</span>
                </div>
            </div>
        `;
    }).join("");
}

function updateStatusBar(status) {
    document.getElementById("status-text").textContent = 
        `Monitoreando ${status.total_channels} canales · Analizando ${status.analyzing}`;
}

async function addChannel() {
    const input = document.getElementById("channel-input");
    const name = input.value.trim();

    if (!name) {
        alert("Ingresa un nombre de canal");
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/channels`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name })
        });

        const data = await response.json();
        if (response.ok) {
            input.value = "";
            fetchChannels();
            fetchStatus();
        } else {
            alert(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error("Error adding channel:", error);
    }
}

async function removeChannel(name) {
    if (!confirm(`¿Remover canal ${name}?`)) return;

    try {
        const response = await fetch(`${API_BASE}/channels/${name}`, {
            method: "DELETE"
        });

        if (response.ok) {
            fetchChannels();
            fetchStatus();
        } else {
            alert("Error removiendo canal");
        }
    } catch (error) {
        console.error("Error removing channel:", error);
    }
}

// Actualizar cada 2 segundos
setInterval(() => {
    fetchChannels();
    fetchEvents();
    fetchStatus();
}, 2000);

// Carga inicial
fetchChannels();
fetchEvents();
fetchStatus();