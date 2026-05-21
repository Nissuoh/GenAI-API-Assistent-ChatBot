const chatBox = document.getElementById('chat-box'), userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn'), uploadBtn = document.getElementById('upload-btn'), fileInput = document.getElementById('file-input');
const calGrid = document.getElementById('calendar-grid'), calMonth = document.getElementById('cal-month');
const resizeHandle = document.getElementById('resize-handle');
const calendarPanel = document.getElementById('calendar-panel');
const chatPanel = document.getElementById('chat-panel');
const toastContainer = document.getElementById('toast-container');

let isProcessing = false, lastHistoryJSON = "";
let currDate = new Date(), viewYear = currDate.getFullYear(), viewMonth = currDate.getMonth();
let currentMonthEvents = [];
let allEvents = [];
let isResizing = false;
let isSpeaking = false;
let selectedCmdIndex = -1;
let showCmdDropdown = false;

const commands = [
    { name: '/heute', desc: 'Termine von heute', action: 'cmd' },
    { name: '/woche', desc: 'Termine diese Woche', action: 'cmd' },
    { name: '/kalender', desc: 'Zum aktuellen Monat', action: 'cmd' },
    { name: '/export', desc: 'Chat exportieren', action: 'cmd' },
    { name: '/tts', desc: 'Letzte Antwort vorlesen', action: 'cmd' },
    { name: '/clear', desc: 'Chat leeren', action: 'cmd' }
];

function escapeHTML(str) { const p = document.createElement('p'); p.textContent = str; return p.innerHTML; }

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = message;
    toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

function showCommandDropdown() {
    const dropdown = document.getElementById('cmd-dropdown');
    dropdown.innerHTML = commands.map((cmd, i) => `
        <div class="cmd-item" data-index="${i}" data-cmd="${cmd.name}">
            <span class="cmd-name">${cmd.name}</span>
            <span class="cmd-desc">${cmd.desc}</span>
        </div>
    `).join('');
    dropdown.classList.remove('hidden');
    showCmdDropdown = true;
    selectedCmdIndex = -1;
    
    dropdown.querySelectorAll('.cmd-item').forEach(item => {
        item.onclick = () => {
            selectCommand(item.dataset.cmd);
        };
    });
}

function hideCommandDropdown() {
    document.getElementById('cmd-dropdown').classList.add('hidden');
    showCmdDropdown = false;
    selectedCmdIndex = -1;
}

function executeCommand(cmdName) {
    hideCommandDropdown();
    
    switch(cmdName) {
        case '/clear':
            chatBox.innerHTML = '';
            lastHistoryJSON = '';
            showToast('Chat geleert', 'success');
            break;
        case '/kalender':
            viewYear = currDate.getFullYear();
            viewMonth = currDate.getMonth();
            loadCalendar();
            showToast('Kalender zurückgesetzt', 'info');
            break;
        case '/export':
            exportChat();
            break;
        case '/tts':
            const botMsgs = [];
            chatBox.querySelectorAll('.message.bot').forEach(m => botMsgs.push(m.textContent));
            if (botMsgs.length > 0) {
                speakText(botMsgs[botMsgs.length - 1]);
            } else {
                showToast('Keine Antwort zum Vorlesen', 'error');
            }
            break;
        case '/heute':
        case '/woche':
            userInput.value = cmdName + ' ';
            userInput.focus();
            break;
        default:
            userInput.value = cmdName + ' ';
            userInput.focus();
    }
}

function selectCommand(cmd) {
    executeCommand(cmd);
}

function updateCmdSelection() {
    const items = document.querySelectorAll('.cmd-item');
    items.forEach((item, i) => {
        item.classList.toggle('selected', i === selectedCmdIndex);
    });
}

function getEventColor(summary) {
    const s = summary.toLowerCase();
    if (s.includes('arbeit') || s.includes('meeting') || s.includes('büro') || s.includes('projekt')) return 'var(--event-arbeit)';
    if (s.includes('geburtstag') || s.includes('feier') || s.includes('urlaub')) return 'var(--event-privat)';
    if (s.includes('arzt') || s.includes('zahnarzt') || s.includes('medizin') || s.includes('fitness')) return 'var(--event-gesundheit)';
    return 'var(--event-standard)';
}

function updateNextEventWidget() {
    const now = new Date();
    const upcoming = allEvents.filter(e => new Date(e.start) > now)
        .sort((a, b) => new Date(a.start) - new Date(b.start));
    
    if (upcoming.length > 0) {
        const next = upcoming[0];
        const nextDate = new Date(next.start);
        const diffMs = nextDate - now;
        const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));
        
        let timeStr;
        if (diffDays === 0) {
            const diffHours = Math.ceil(diffMs / (1000 * 60 * 60));
            timeStr = diffHours <= 1 ? 'In weniger als einer Stunde' : `In ${diffHours} Stunden`;
        } else if (diffDays === 1) {
            timeStr = 'Morgen';
        } else {
            timeStr = `In ${diffDays} Tagen`;
        }
        
        document.getElementById('next-event-name').textContent = next.summary;
        document.getElementById('next-event-time').textContent = timeStr;
        document.getElementById('next-event-widget').style.display = 'block';
    } else {
        document.getElementById('next-event-widget').style.display = 'none';
    }
}

function renderMarkdown(text) {
    let html = escapeHTML(text);
    
    // 1. Code-Blöcke vorübergehend extrahieren und sichern
    const codeBlocks = [];
    html = html.replace(/```([\s\S]*?)```/g, (match, code) => {
        const placeholder = `__LUMINA_CODE_BLOCK_${codeBlocks.length}__`;
        codeBlocks.push(code);
        return placeholder;
    });

    // 2. Inline-Markdown auf dem verbleibenden Fließtext anwenden
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');

    // 3. Listen zeilenweise verarbeiten, um gieriges Verschachteln zu verhindern
    const lines = html.split('\n');
    let inList = false;
    for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        if (line.startsWith('- ')) {
            const content = line.substring(2).trim();
            if (!inList) {
                lines[i] = '<ul><li>' + content + '</li>';
                inList = true;
            } else {
                lines[i] = '<li>' + content + '</li>';
            }
        } else {
            if (inList) {
                lines[i - 1] += '</ul>';
                inList = false;
            }
        }
    }
    if (inList) {
        lines[lines.length - 1] += '</ul>';
    }
    html = lines.join('\n');

    // 4. Zeilenumbrüche in <br> umwandeln, aber nicht um Listen-Tags herum
    html = html.replace(/\n/g, '<br>');
    html = html.replace(/(<\/?[ul|li]>)\s*<br>/gi, '$1');
    html = html.replace(/<br>\s*(<\/?[ul|li]>)/gi, '$1');

    // 5. Code-Blöcke unbeschädigt wieder einsetzen (Callback verhindert Interpolationsfehler mit $)
    codeBlocks.forEach((code, index) => {
        const placeholder = `__LUMINA_CODE_BLOCK_${index}__`;
        html = html.replace(placeholder, () => `<pre><code>${code}</code></pre>`);
    });

    return html;
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Kopiert!', 'success');
    }).catch(() => {
        showToast('Kopieren fehlgeschlagen', 'error');
    });
}

function getMessageCleanText(msgEl) {
    const clone = msgEl.cloneNode(true);
    const actions = clone.querySelector('.message-actions');
    if (actions) actions.remove();
    return (clone.innerText || clone.textContent || "").trim();
}

function copyMessageText(btnElement) {
    const msgEl = btnElement.closest('.message');
    if (!msgEl) return;
    copyToClipboard(getMessageCleanText(msgEl));
}

function speakMessageText(btnElement) {
    const msgEl = btnElement.closest('.message');
    if (!msgEl) return;
    speakText(getMessageCleanText(msgEl));
}

function speakText(text) {
    if ('speechSynthesis' in window) {
        if (isSpeaking) {
            speechSynthesis.cancel();
            isSpeaking = false;
            return;
        }
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'de-DE';
        utterance.rate = 1;
        utterance.onend = () => { isSpeaking = false; };
        speechSynthesis.speak(utterance);
        isSpeaking = true;
        showToast('Vorlesen gestartet', 'info');
    } else {
        showToast('Text-to-Speech nicht unterstützt', 'error');
    }
}

function exportChat() {
    const messages = [];
    chatBox.querySelectorAll('.message').forEach(msg => {
        const role = msg.classList.contains('user') ? 'Du' : 'Lumina';
        const actions = msg.querySelector('.message-actions');
        let text = msg.textContent;
        if (actions) text = text.replace(actions.textContent, '').trim();
        messages.push(`${role}: ${text}`);
    });
    
    const blob = new Blob([messages.join('\n\n')], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lumina-chat-${new Date().toISOString().split('T')[0]}.txt`;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Chat exportiert!', 'success');
}

resizeHandle.addEventListener('mousedown', (e) => {
    isResizing = true;
    resizeHandle.classList.add('active');
    document.body.classList.add('resizing');
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
});

document.addEventListener('mousemove', (e) => {
    if (!isResizing) return;
    
    requestAnimationFrame(() => {
        const container = document.querySelector('.content-row');
        if (!container) return;
        const containerWidth = container.offsetWidth;
        const calendarWidth = e.clientX - container.getBoundingClientRect().left;
        
        const minCal = 220;
        const minChat = 400;
        const maxCal = containerWidth - minChat;
        
        const newCalWidth = Math.max(minCal, Math.min(maxCal, calendarWidth));
        
        calendarPanel.style.width = newCalWidth + 'px';
        calendarPanel.style.flex = 'none';
        chatPanel.style.flex = '1 1 auto';
        chatPanel.style.minWidth = minChat + 'px';
    });
});

document.addEventListener('mouseup', () => {
    if (isResizing) {
        isResizing = false;
        resizeHandle.classList.remove('active');
        document.body.classList.remove('resizing');
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
});

function updateThemeIcon() {
    const isDark = document.body.classList.contains('dark-mode');
    const toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {
        if (isDark) {
            toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-sun"><circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/><path d="m19.07 4.93-1.41 1.41"/></svg>`;
            toggleBtn.title = "Lichtmodus einschalten";
        } else {
            toggleBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-moon"><path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/></svg>`;
            toggleBtn.title = "Dunkelmodus einschalten";
        }
    }
}

if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-mode');
}
updateThemeIcon();

document.getElementById('theme-toggle').onclick = () => {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
    updateThemeIcon();
};

document.getElementById('tts-btn').onclick = () => {
    const botMsgs = [];
    chatBox.querySelectorAll('.message.bot').forEach(m => botMsgs.push(m.textContent));
    if (botMsgs.length > 0) speakText(botMsgs[botMsgs.length - 1]);
};

document.getElementById('export-btn').onclick = exportChat;

document.getElementById('cal-today').onclick = () => {
    viewYear = currDate.getFullYear();
    viewMonth = currDate.getMonth();
    loadCalendar();
};

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        document.getElementById('day-modal').classList.add('hidden');
        const helpModal = document.getElementById('help-modal');
        if (helpModal) helpModal.classList.add('hidden');
    }
    
    // Calendar Keyboard Navigation (ArrowLeft/ArrowRight for months, 'H' for today)
    if (document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'TEXTAREA') {
        const tabCalendar = document.getElementById('tab-calendar');
        if (tabCalendar && tabCalendar.classList.contains('active')) {
            if (e.key === 'ArrowLeft') {
                e.preventDefault();
                document.getElementById('cal-prev').click();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                document.getElementById('cal-next').click();
            } else if (e.key.toLowerCase() === 'h') {
                e.preventDefault();
                document.getElementById('cal-today').click();
            }
        }
    }

    if (e.ctrlKey && e.key === 'Enter') {
        e.preventDefault();
        sendMessage();
    }
});

async function loadCalendar() {
    calMonth.innerText = new Date(viewYear, viewMonth).toLocaleDateString('de-DE', { month: 'long', year: 'numeric' });
    try {
        const res = await fetch(`/calendar?year=${viewYear}&month=${viewMonth + 1}`);
        const data = await res.json();
        currentMonthEvents = data.events || [];
        allEvents = [...allEvents, ...currentMonthEvents].filter((e, i, a) => 
            a.findIndex(x => x.start === e.start && x.summary === e.summary) === i
        );
        renderGrid();
        updateNextEventWidget();
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

        let eventsHtml = '';
        if (dayEvents.length > 0) {
            eventsHtml = dayEvents.slice(0, 3).map(e => {
                const shortTitle = e.summary.length > 15 ? e.summary.substring(0, 15) + '…' : e.summary;
                const colorVar = getEventColor(e.summary);
                const category = colorVar.replace('var(--event-', '').replace(')', '');
                return `<div class="cal-event category-${category}" title="${escapeHTML(e.summary)}">${escapeHTML(shortTitle)}</div>`;
            }).join('');
            if (dayEvents.length > 3) {
                eventsHtml += `<div class="cal-event-more">+${dayEvents.length - 3}</div>`;
            }
        }

        html += `<div class="cal-cell ${isToday ? 'today' : ''} ${dayEvents.length > 0 ? 'has-events' : ''}" data-day="${d}">
            <div class="cal-day-num">${d}</div>
            <div class="cal-events-list">${eventsHtml}</div>
        </div>`;
    }
    calGrid.innerHTML = html;

    document.querySelectorAll('.cal-cell[data-day]').forEach(cell => {
        cell.onclick = () => {
            document.querySelectorAll('.cal-cell').forEach(c => c.classList.remove('selected'));
            cell.classList.add('selected');
            openDayModal(parseInt(cell.getAttribute('data-day')));
        };
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
            const color = getEventColor(e.summary);
            return `<div class="event-item" style="border-left: 4px solid ${color}"><span class="event-time">${timeStr}</span><span class="event-title">${escapeHTML(e.summary)}</span></div>`;
        }).join('');
    }

    document.getElementById('day-modal').classList.remove('hidden');
}

document.getElementById('close-modal').onclick = () => {
    document.getElementById('day-modal').classList.add('hidden');
    document.querySelectorAll('.cal-cell').forEach(c => c.classList.remove('selected'));
};
document.getElementById('day-modal').onclick = (e) => {
    if (e.target === document.getElementById('day-modal')) {
        document.getElementById('day-modal').classList.add('hidden');
        document.querySelectorAll('.cal-cell').forEach(c => c.classList.remove('selected'));
    }
};

document.getElementById('cal-prev').onclick = () => { viewMonth--; if (viewMonth < 0) { viewMonth = 11; viewYear--; } loadCalendar(); };
document.getElementById('cal-next').onclick = () => { viewMonth++; if (viewMonth > 11) { viewMonth = 0; viewYear++; } loadCalendar(); };

function appendMessage(role, text) {
    const d = document.createElement('div');
    d.className = `message ${role === 'assistant' || role === 'bot' ? 'bot' : 'user'}`;
    
    if (text.startsWith("IMG_CONFIRM:") || text.startsWith("FILE_CONFIRM:") || text.startsWith("VOICE_CONFIRM:")) {
        if (text.startsWith("VOICE_CONFIRM:")) {
            const parts = text.replace(/^VOICE_CONFIRM:/, "").split("|");
            const url = parts[0];
            const transcript = parts.slice(1).join("|");
            
            d.innerHTML = `
                <div class="voice-message-container">
                    <div class="voice-player-row">
                        <span class="voice-icon">🎤</span>
                        <audio src="${url}" controls class="voice-audio-player"></audio>
                    </div>
                    <div class="voice-transcript">
                        <span class="transcript-label">Transkript:</span>
                        <p class="transcript-text">"${escapeHTML(transcript)}"</p>
                    </div>
                </div>
            `;
        } else {
            const [url, uText] = text.replace(/^(IMG|FILE)_CONFIRM:/, "").split("|");
            d.innerHTML = text.startsWith("IMG_CONFIRM:") 
                ? `<img src="${url}" class="chat-img" onclick="window.open('${url}')"><br>${escapeHTML(uText || '')}` 
                : `📄 <a href="${url}" target="_blank">Dokument</a><br>${escapeHTML(uText || '')}`;
        }
    } else {
        d.innerHTML = renderMarkdown(text);
    }
    
    if (role === 'assistant' || role === 'bot') {
        const actions = document.createElement('div');
        actions.className = 'message-actions';
        actions.innerHTML = `
            <button class="msg-action-btn" onclick="copyMessageText(this)" title="Nachricht kopieren">📋 Kopieren</button>
            <button class="msg-action-btn" onclick="speakMessageText(this)" title="Nachricht vorlesen">🔊 Vorlesen</button>
        `;
        d.appendChild(actions);
    }
    
    chatBox.appendChild(d);
}

function appendTypingIndicator() {
    const l = document.createElement('div');
    l.className = 'message bot';
    l.id = 'typing-indicator';
    l.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    chatBox.appendChild(l);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function removeTypingIndicator() {
    const l = document.getElementById('typing-indicator');
    if (l) l.remove();
}

async function refreshChat() {
    if (isProcessing) return;
    try {
        const h = await (await fetch('/history')).json(), cJSON = JSON.stringify(h);
        if (cJSON !== lastHistoryJSON) {
            const isAtBottom = chatBox.scrollHeight - chatBox.clientHeight <= chatBox.scrollTop + 50;

            chatBox.innerHTML = '';
            h.forEach(m => appendMessage(m.role, m.content));
            lastHistoryJSON = cJSON;

            if (isAtBottom) chatBox.scrollTop = chatBox.scrollHeight;
            loadCalendar();
            loadNotes();
        }
    } catch { }
}

async function sendMessage() {
    const rawInput = userInput.value;
    const m = rawInput.trim(); 
    
    if (!m || isProcessing) return;
    
    isProcessing = true; 
    userInput.value = '';
    appendMessage('user', m);
    chatBox.scrollTop = chatBox.scrollHeight;
    appendTypingIndicator();

    try { 
        await fetch('/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: m }) }); 
        await refreshChat(); 
        showToast('Nachricht gesendet', 'success');
    }
    catch (e) { 
        showToast('Fehler beim Senden', 'error'); 
    }
    finally { 
        removeTypingIndicator();
        isProcessing = false; 
        loadCalendar(); 
        chatBox.scrollTop = chatBox.scrollHeight; 
    }
}

sendBtn.onclick = sendMessage; 

userInput.addEventListener('input', (e) => {
    const value = e.target.value;
    
    if (value === '') {
        hideCommandDropdown();
        return;
    }
    
    if (!value.startsWith('/')) {
        hideCommandDropdown();
        return;
    }
    
    const filtered = commands.filter(c => c.name.startsWith(value.toLowerCase()));
    const dropdown = document.getElementById('cmd-dropdown');
    
    if (filtered.length === 0) {
        hideCommandDropdown();
        return;
    }
    
    dropdown.innerHTML = filtered.map((cmd, i) => `
        <div class="cmd-item" data-index="${i}" data-cmd="${cmd.name}">
            <span class="cmd-name">${cmd.name}</span>
            <span class="cmd-desc">${cmd.desc}</span>
        </div>
    `).join('');
    
    dropdown.classList.remove('hidden');
    showCmdDropdown = true;
    selectedCmdIndex = -1;
    
    dropdown.querySelectorAll('.cmd-item').forEach(item => {
        item.onclick = () => selectCommand(item.dataset.cmd);
    });
});

userInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        
        if (showCmdDropdown && selectedCmdIndex >= 0) {
            const items = document.querySelectorAll('.cmd-item');
            executeCommand(items[selectedCmdIndex].dataset.cmd);
        } else {
            sendMessage();
        }
        return;
    }
    
    if (!showCmdDropdown) return;
    
    const items = document.querySelectorAll('.cmd-item');
    if (items.length === 0) return;
    
    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedCmdIndex = Math.min(selectedCmdIndex + 1, items.length - 1);
        updateCmdSelection();
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedCmdIndex = Math.max(selectedCmdIndex - 1, 0);
        updateCmdSelection();
    } else if (e.key === 'Escape') {
        hideCommandDropdown();
    }
});

userInput.addEventListener('blur', () => {
    setTimeout(hideCommandDropdown, 150);
});

uploadBtn.onclick = () => fileInput.click();
fileInput.onchange = async () => {
    if (!fileInput.files[0]) return;
    const fd = new FormData(); 
    fd.append('file', fileInput.files[0]); 
    fd.append('message', userInput.value);
    isProcessing = true; 
    userInput.value = '';
    appendTypingIndicator();

    try { 
        await fetch('/upload', { method: 'POST', body: fd }); 
        await refreshChat(); 
        showToast('Datei hochgeladen', 'success');
    }
    catch (e) { 
        showToast('Upload fehlgeschlagen', 'error'); 
    }
    finally { 
        removeTypingIndicator();
        isProcessing = false; 
        fileInput.value = ''; 
        loadCalendar(); 
        chatBox.scrollTop = chatBox.scrollHeight; 
    }
};

const chatSection = document.getElementById('chat-panel');
chatSection.addEventListener('dragover', (e) => {
    e.preventDefault();
    chatSection.classList.add('drag-over');
});

chatSection.addEventListener('dragleave', () => {
    chatSection.classList.remove('drag-over');
});

chatSection.addEventListener('drop', (e) => {
    e.preventDefault();
    chatSection.classList.remove('drag-over');
    
    if (e.dataTransfer.files.length > 0) {
        fileInput.files = e.dataTransfer.files;
        fileInput.dispatchEvent(new Event('change'));
    }
});

// --- NOTEPAD TABS AND LOGIC (Lumina Obsidian Style) ---
const tabCalendar = document.getElementById('tab-calendar');
const tabNotepad = document.getElementById('tab-notepad');
const calendarView = document.getElementById('calendar-view');
const notepadView = document.getElementById('notepad-view');

tabCalendar.onclick = () => {
    tabCalendar.classList.add('active');
    tabNotepad.classList.remove('active');
    calendarView.classList.add('active-view');
    calendarView.classList.remove('hidden-view');
    notepadView.classList.add('hidden-view');
    notepadView.classList.remove('active-view');
    loadCalendar();
};

tabNotepad.onclick = () => {
    tabNotepad.classList.add('active');
    tabCalendar.classList.remove('active');
    notepadView.classList.add('active-view');
    notepadView.classList.remove('hidden-view');
    calendarView.classList.add('hidden-view');
    calendarView.classList.remove('active-view');
    loadNotes();
};

const notesList = document.getElementById('notes-list');
const noteInput = document.getElementById('note-input');
const addNoteBtn = document.getElementById('add-note-btn');

async function loadNotes() {
    try {
        const res = await fetch('/notes');
        const data = await res.json();
        renderNotes(data.notes || []);
    } catch (e) {
        console.error("Fehler beim Laden der Notizen:", e);
    }
}

function renderNotes(notes) {
    if (notes.length === 0) {
        notesList.innerHTML = `
            <div style="text-align: center; color: var(--text-muted); padding: 40px 10px; font-size: 0.9rem;">
                Der Notizblock ist leer.<br>
                Sag Lumina z.B.: "Erinnere mich an Milch kaufen".
            </div>
        `;
        return;
    }
    
    notesList.innerHTML = notes.map(note => {
        let dateStr = "";
        try {
            if (note.created_at) {
                const date = new Date(note.created_at.replace(" ", "T") + "Z");
                dateStr = date.toLocaleDateString('de-DE', {
                    day: '2-digit',
                    month: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                });
            }
        } catch(err) {
            dateStr = note.created_at;
        }

        return `
            <div class="note-item" id="note-${note.id}">
                <div class="note-content">
                    <div>${escapeHTML(note.content)}</div>
                    <div class="note-date">${dateStr}</div>
                </div>
                <button class="delete-note-btn" onclick="deleteNote(${note.id})" title="Notiz löschen">
                    <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-trash-2"><path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/></svg>
                </button>
            </div>
        `;
    }).join('');
}

async function addManualNote() {
    const text = noteInput.value.trim();
    if (!text) return;
    noteInput.value = '';
    
    try {
        const res = await fetch('/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: text })
        });
        if (res.ok) {
            showToast('Notiz hinzugefügt', 'success');
            loadNotes();
        } else {
            showToast('Fehler beim Hinzufügen', 'error');
        }
    } catch (e) {
        showToast('Fehler beim Hinzufügen', 'error');
    }
}

async function deleteNote(noteId) {
    if (!confirm('Möchtest du diese Notiz wirklich löschen?')) return;
    try {
        const res = await fetch(`/notes/${noteId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Notiz gelöscht', 'success');
            loadNotes();
        } else {
            showToast('Fehler beim Löschen', 'error');
        }
    } catch (e) {
        showToast('Fehler beim Löschen', 'error');
    }
}

// Global machen für die onclick-Events
window.deleteNote = deleteNote;

addNoteBtn.onclick = addManualNote;
noteInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        e.preventDefault();
        addManualNote();
    }
});

// --- SPEECH RECOGNITION & AUDIO RECORDING ---
let recognition = null;
let mediaRecorder = null;
let audioChunks = [];
let userMediaStream = null;
let isRecording = false;
let recordTimerInterval = null;
let recordSeconds = 0;

function formatTime(sec) {
    const m = Math.floor(sec / 60).toString().padStart(2, '0');
    const s = (sec % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
}

async function toggleSpeechRecognition() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        showToast('Spracherkennung in diesem Browser nicht unterstützt. Bitte nutze Chrome, Edge oder Safari.', 'error');
        return;
    }

    const micBtnEl = document.getElementById('mic-btn');

    if (isRecording) {
        // Stop recording
        if (recognition) {
            recognition.stop();
        }
        return;
    }

    if (isProcessing) {
        showToast('Bitte warte, bis die aktuelle Anfrage fertig ist.', 'info');
        return;
    }

    try {
        // Request microphone permission and hold the stream
        userMediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
        console.error('Microphone permission denied:', e);
        showToast('Mikrofon-Zugriff verweigert oder kein Mikrofon gefunden.', 'error');
        return;
    }

    try {
        // Set up MediaRecorder
        audioChunks = [];
        mediaRecorder = new MediaRecorder(userMediaStream);
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        recognition = new SpeechRecognition();
        recognition.lang = 'de-DE';
        recognition.continuous = true;
        recognition.interimResults = false;

        let accumulatedTranscript = '';

        recognition.onstart = () => {
            isRecording = true;
            recordSeconds = 0;
            userInput.placeholder = `Sprachaufnahme läuft... [00:00]`;
            userInput.disabled = true;

            if (micBtnEl) {
                micBtnEl.classList.add('recording');
                micBtnEl.title = "Aufnahme stoppen und senden";
            }

            showToast('Sprachnotiz-Aufnahme gestartet...', 'info');

            // Start timer
            recordTimerInterval = setInterval(() => {
                recordSeconds++;
                userInput.placeholder = `Sprachaufnahme läuft... [${formatTime(recordSeconds)}]`;
            }, 1000);
            
            // Start MediaRecorder
            mediaRecorder.start();
        };

        recognition.onresult = (event) => {
            for (let i = event.resultIndex; i < event.results.length; ++i) {
                if (event.results[i].isFinal) {
                    accumulatedTranscript += event.results[i][0].transcript + ' ';
                }
            }
        };

        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            if (event.error !== 'no-speech') {
                showToast(`Fehler bei der Spracherkennung: ${event.error}`, 'error');
            }
        };

        recognition.onend = async () => {
            // Clean up timer
            if (recordTimerInterval) {
                clearInterval(recordTimerInterval);
                recordTimerInterval = null;
            }

            // Stop media recorder
            if (mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
            
            // Stop tracks to release mic hardware
            if (userMediaStream) {
                userMediaStream.getTracks().forEach(track => track.stop());
            }

            // Reset UI
            if (micBtnEl) {
                micBtnEl.classList.remove('recording');
                micBtnEl.title = "Sprachnachricht aufnehmen";
            }
            userInput.placeholder = "Nachricht an Lumina...";
            userInput.disabled = false;
            isRecording = false;

            const textToSend = accumulatedTranscript.trim();
            if (!textToSend) {
                showToast('Keine Sprache erkannt oder Aufnahme leer.', 'warning');
                return;
            }

            // Set up MediaRecorder onstop callback to handle uploading once chunks are assembled
            mediaRecorder.onstop = async () => {
                isProcessing = true;
                appendTypingIndicator();

                try {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const fd = new FormData();
                    fd.append('file', audioBlob, 'voice.webm');
                    fd.append('transcript', textToSend);

                    const res = await fetch('/voice-record', {
                        method: 'POST',
                        body: fd
                    });

                    if (res.ok) {
                        showToast('Sprachnachricht erfolgreich gesendet', 'success');
                        await refreshChat();
                    } else {
                        const errData = await res.json().catch(() => ({}));
                        showToast(errData.detail || 'Fehler bei der Sprachverarbeitung', 'error');
                    }
                } catch (e) {
                    console.error('Upload error:', e);
                    showToast('Upload-Fehler bei der Sprachnachricht', 'error');
                } finally {
                    removeTypingIndicator();
                    isProcessing = false;
                    loadCalendar();
                    loadNotes();
                    chatBox.scrollTop = chatBox.scrollHeight;
                }
            };
        };

        recognition.start();

    } catch (e) {
        console.error('Error starting SpeechRecognition:', e);
        showToast('Fehler beim Starten der Sprachaufnahme', 'error');
    }
}

const micBtn = document.getElementById('mic-btn');
if (micBtn) {
    micBtn.onclick = toggleSpeechRecognition;
}

loadCalendar(); 
loadNotes();
setInterval(refreshChat, 3000); 
setInterval(loadCalendar, 30000);

