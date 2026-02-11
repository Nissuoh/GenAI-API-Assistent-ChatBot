const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let isProcessing = false; // Verhindert Mehrfach-Senden

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true; // Button deaktivieren

    appendMessage('user', message);
    userInput.value = '';

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot';
    loadingDiv.innerText = 'KI denkt nach...';
    chatBox.appendChild(loadingDiv);

    try {
        const response = await fetch(`/chat?message=${encodeURIComponent(message)}`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Netzwerk-Antwort war nicht ok');

        const data = await response.json();
        chatBox.removeChild(loadingDiv);

        // Anzeige, welche KI geantwortet hat (optional)
        const sourceInfo = data.source ? ` [${data.source}]` : '';
        appendMessage('bot', data.response + sourceInfo);

    } catch (error) {
        if (chatBox.contains(loadingDiv)) chatBox.removeChild(loadingDiv);
        appendMessage('bot', 'Fehler: Server nicht erreichbar oder Zeitüberschreitung.');
    } finally {
        isProcessing = false;
        sendBtn.disabled = false; // Button wieder freigeben
        userInput.focus();
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;
    msgDiv.innerText = text;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});