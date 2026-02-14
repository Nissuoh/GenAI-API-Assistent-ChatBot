const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let isProcessing = false;
let chatHistory = []; // Speichert den Verlauf für das Trinity-Modell

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;

    appendMessage('user', message);
    userInput.value = '';

    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'message bot loading';
    loadingDiv.innerText = 'KI denkt nach...';
    chatBox.appendChild(loadingDiv);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                history: chatHistory
            })
        });

        if (!response.ok) throw new Error('Server-Fehler');

        const data = await response.json();
        chatBox.removeChild(loadingDiv);

        // 1. Falls vorhanden: Denkprozess (Reasoning) anzeigen
        if (data.reasoning) {
            appendMessage('reasoning', data.reasoning);
        }

        // 2. Hauptantwort anzeigen
        const sourceTag = data.source ? ` (${data.source})` : '';
        appendMessage('bot', data.content + sourceTag);

        // 3. Verlauf aktualisieren (für Kontext im nächsten Schritt)
        chatHistory.push({ role: "user", content: message });
        chatHistory.push({
            role: "assistant",
            content: data.content,
            reasoning_details: data.reasoning
        });

        // Verlauf begrenzen, damit die API-Requests nicht zu groß werden
        if (chatHistory.length > 10) chatHistory.shift();

    } catch (error) {
        if (chatBox.contains(loadingDiv)) chatBox.removeChild(loadingDiv);
        appendMessage('bot', 'Fehler: Verbindung zum Server fehlgeschlagen.');
    } finally {
        isProcessing = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
}

function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

    // Bei Reasoning nutzen wir ein spezielles Styling
    if (role === 'reasoning') {
        msgDiv.innerHTML = `<small><strong>Gedankengang:</strong></small><br>${text.replace(/\n/g, '<br>')}`;
        msgDiv.style.opacity = "0.7";
        msgDiv.style.fontSize = "0.85em";
        msgDiv.style.borderLeft = "3px solid #ddd";
        msgDiv.style.paddingLeft = "10px";
        msgDiv.style.marginBottom = "5px";
    } else {
        msgDiv.innerText = text;
    }

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});