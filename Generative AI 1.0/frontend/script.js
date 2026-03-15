const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const fileInput = document.getElementById('file-input');
const uploadBtn = document.getElementById('upload-btn');
const themeToggle = document.getElementById('theme-toggle');

let isProcessing = false;
let lastHistoryJSON = "";

// Theme Management
if (localStorage.getItem('theme') === 'dark') {
    document.body.classList.add('dark-mode');
}
themeToggle.onclick = () => {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('theme', document.body.classList.contains('dark-mode') ? 'dark' : 'light');
};

function escapeHTML(str) {
    const p = document.createElement('p');
    p.textContent = str;
    return p.innerHTML;
}

function appendMessage(role, text, smoothScroll = true) {
    const msgDiv = document.createElement('div');
    const isBot = (role === 'assistant' || role === 'bot');
    msgDiv.className = `message ${isBot ? 'bot' : 'user'}`;

    if (text.startsWith("IMG_CONFIRM:") || text.startsWith("FILE_CONFIRM:")) {
        const isImage = text.startsWith("IMG_CONFIRM:");
        const content = text.replace(isImage ? "IMG_CONFIRM:" : "FILE_CONFIRM:", "");
        const [fileUrl, userText] = content.split("|");

        if (isImage) {
            msgDiv.innerHTML = `
                <div style="display: flex; flex-direction: column;">
                    <img src="${fileUrl}" class="chat-img" onclick="window.open('${fileUrl}')">
                    <span>${userText ? escapeHTML(userText) : ''}</span>
                </div>`;
        } else {
            msgDiv.innerHTML = `📄 <a href="${fileUrl}" target="_blank" style="color: inherit; font-weight: bold;">Dokument ansehen</a><br>${escapeHTML(userText || '')}`;
        }
    } else {
        msgDiv.innerHTML = escapeHTML(text).replace(/\n/g, '<br>');
    }

    chatBox.appendChild(msgDiv);
    if (smoothScroll) {
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

async function refreshChat() {
    if (isProcessing) return;
    try {
        const response = await fetch('/history');
        const history = await response.json();
        const currentJSON = JSON.stringify(history);

        if (currentJSON !== lastHistoryJSON) {
            chatBox.innerHTML = '';
            history.forEach(msg => appendMessage(msg.role, msg.content, false));
            lastHistoryJSON = currentJSON;
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    } catch (e) {
        console.error("History Refresh Fehler", e);
    }
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    userInput.value = '';
    appendMessage('user', message);

    const loader = document.createElement('div');
    loader.className = 'message bot';
    loader.innerHTML = '<span class="loading-dots">Lumina schreibt</span>';
    chatBox.appendChild(loader);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        if (!res.ok) throw new Error();
        await refreshChat();
    } catch (err) {
        appendMessage('bot', '⚠️ Fehler: Server nicht erreichbar.');
    } finally {
        if (chatBox.contains(loader)) loader.remove();
        isProcessing = false;
    }
}

sendBtn.onclick = sendMessage;
userInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };
uploadBtn.onclick = () => fileInput.click();

fileInput.onchange = async () => {
    const file = fileInput.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    formData.append('message', userInput.value);

    isProcessing = true;
    userInput.value = '';

    const loader = document.createElement('div');
    loader.className = 'message bot';
    loader.innerHTML = '<span class="loading-dots">Datei wird analysiert</span>';
    chatBox.appendChild(loader);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        await fetch('/upload', { method: 'POST', body: formData });
        await refreshChat();
    } catch (e) {
        appendMessage('bot', '❌ Upload fehlgeschlagen.');
    } finally {
        if (chatBox.contains(loader)) loader.remove();
        isProcessing = false;
        fileInput.value = '';
    }
};

setInterval(refreshChat, 3000);
window.onload = refreshChat;