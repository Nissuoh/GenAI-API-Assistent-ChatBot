const chatBox = document.getElementById('chat-box'), userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn'), uploadBtn = document.getElementById('upload-btn'), fileInput = document.getElementById('file-input');
const calGrid = document.getElementById('calendar-grid'), calMonth = document.getElementById('cal-month');

let isProcessing = false, lastHistoryJSON = "";
let currDate = new Date(), viewYear = currDate.getFullYear(), viewMonth = currDate.getMonth();
let currentMonthEvents = [];

if (localStorage.getItem('theme') === 'dark') document.body.classList.add('dark-mode');
document.getElementById('theme-toggle').onclick = () => {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
};

function escapeHTML(str) { const p = document.createElement('p'); p.textContent = str; return p.innerHTML; }

async function loadCalendar() {
    calMonth.innerText = new Date(viewYear, viewMonth).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
    try {
        const res = await fetch(`/calendar?year=${viewYear}&month=${viewMonth + 1}`);
        const data = await res.json();
        currentMonthEvents = data.events || [];
        renderGrid();
    } catch {
        currentMonthEvents = [];
        renderGrid();
    }
}

function renderGrid() {
    let html = '';
    const firstDay = new Date(viewYear, viewMonth, 1).getDay();
    const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
    const emptyCells = firstDay === 0 ? 6 : firstDay - 1;

    for (let i = 0; i < emptyCells; i++) html += `<div class="cal-cell empty"></div>`;

    for (let d = 1; d <= daysInMonth; d++) {
        const isToday = d === currDate.getDate() && viewMonth === currDate.getMonth() && viewYear === currDate.getFullYear();
        const dayEvents = currentMonthEvents.filter(e => {
            const ed = new Date(e.start);
            return ed.getDate() === d && ed.getMonth() === viewMonth && ed.getFullYear() === viewYear;
        });

        const dot = dayEvents.length > 0 ? `<div class="event-dot"></div>` : '';
        html += `<div class="cal-cell ${isToday ? 'today' : ''}" data-day="${d}">${d}${dot}</div>`;
    }
    calGrid.innerHTML = html;

    document.querySelectorAll('.cal-cell[data-day]').forEach(cell => {
        cell.onclick = () => openDayModal(parseInt(cell.getAttribute('data-day')));
    });
}

function openDayModal(day) {
    const dayEvents = currentMonthEvents.filter(e => {
        const ed = new Date(e.start);
        return ed.getDate() === day && ed.getMonth() === viewMonth && ed.getFullYear() === viewYear;
    });

    const dateStr = new Date(viewYear, viewMonth, day).toLocaleDateString('de-DE', { weekday: 'short', day: '2-digit', month: 'long' });
    document.getElementById('modal-date-title').innerText = dateStr;
    const list = document.getElementById('modal-events-list');

    if (dayEvents.length === 0) {
        list.innerHTML = '<p class="no-events">Keine Termine an diesem Tag.</p>';
    } else {
        list.innerHTML = dayEvents.map(e => {
            const isAllDay = e.start.length <= 10;
            const timeStr = isAllDay ? 'Ganztägig' : new Date(e.start).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
            return `<div class="event-item"><span class="event-time">${timeStr}</span><span class="event-title">${escapeHTML(e.summary)}</span></div>`;
        }).join('');
    }

    document.getElementById('day-modal').classList.remove('hidden');
}

document.getElementById('close-modal').onclick = () => document.getElementById('day-modal').classList.add('hidden');
document.getElementById('day-modal').onclick = (e) => { if (e.target === document.getElementById('day-modal')) document.getElementById('day-modal').classList.add('hidden'); };

document.getElementById('cal-prev').onclick = () => { viewMonth--; if (viewMonth < 0) { viewMonth = 11; viewYear--; } loadCalendar(); };
document.getElementById('cal-next').onclick = () => { viewMonth++; if (viewMonth > 11) { viewMonth = 0; viewYear++; } loadCalendar(); };

function appendMessage(role, text) {
    const d = document.createElement('div');
    d.className = `message ${role === 'assistant' || role === 'bot' ? 'bot' : 'user'}`;
    if (text.startsWith("IMG_CONFIRM:") || text.startsWith("FILE_CONFIRM:")) {
        const [url, uText] = text.replace(/^(IMG|FILE)_CONFIRM:/, "").split("|");
        d.innerHTML = text.startsWith("IMG_CONFIRM:") ? `<img src="${url}" class="chat-img" onclick="window.open('${url}')"><br>${escapeHTML(uText || '')}` : `📄 <a href="${url}" target="_blank">Dokument</a><br>${escapeHTML(uText || '')}`;
    } else { d.innerHTML = escapeHTML(text).replace(/\n/g, '<br>'); }
    chatBox.appendChild(d);
}

async function refreshChat() {
    if (isProcessing) return;
    try {
        const h = await (await fetch('/history')).json(), cJSON = JSON.stringify(h);
        if (cJSON !== lastHistoryJSON) {
            // Prüfen, ob der Nutzer am Ende des Chats ist (Toleranz: 50px)
            const isAtBottom = chatBox.scrollHeight - chatBox.clientHeight <= chatBox.scrollTop + 50;

            chatBox.innerHTML = '';
            h.forEach(m => appendMessage(m.role, m.content));
            lastHistoryJSON = cJSON;

            // Nur automatisch scrollen, wenn der Nutzer bereits unten war
            if (isAtBottom) chatBox.scrollTop = chatBox.scrollHeight;

            loadCalendar();
        }
    } catch { }
}

async function sendMessage() {
    const m = userInput.value.trim(); if (!m || isProcessing) return;
    isProcessing = true; userInput.value = '';
    appendMessage('user', m);

    // Nach eigener Eingabe immer ans Ende scrollen
    chatBox.scrollTop = chatBox.scrollHeight;

    const l = document.createElement('div'); l.className = 'message bot'; l.innerText = 'Lumina tippt...'; chatBox.appendChild(l);
    chatBox.scrollTop = chatBox.scrollHeight;

    try { await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: m }) }); await refreshChat(); }
    finally { l.remove(); isProcessing = false; loadCalendar(); chatBox.scrollTop = chatBox.scrollHeight; }
}

sendBtn.onclick = sendMessage; userInput.onkeypress = e => { if (e.key === 'Enter') sendMessage(); };
uploadBtn.onclick = () => fileInput.click();
fileInput.onchange = async () => {
    if (!fileInput.files[0]) return;
    const fd = new FormData(); fd.append('file', fileInput.files[0]); fd.append('message', userInput.value);
    isProcessing = true; userInput.value = '';
    const l = document.createElement('div'); l.className = 'message bot'; l.innerText = 'Upload läuft...'; chatBox.appendChild(l);

    chatBox.scrollTop = chatBox.scrollHeight;

    try { await fetch('/upload', { method: 'POST', body: fd }); await refreshChat(); }
    finally { l.remove(); isProcessing = false; fileInput.value = ''; loadCalendar(); chatBox.scrollTop = chatBox.scrollHeight; }
};

loadCalendar(); setInterval(refreshChat, 3000); setInterval(loadCalendar, 30000);