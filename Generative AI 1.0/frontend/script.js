const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');

let isProcessing = false;
let lastMessageCount = 0; // Merkt sich, wie viele Nachrichten wir schon haben

// 1. Funktion: Nachricht im Interface anzeigen
function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${role}`;

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

// 2. Echtzeit-Funktion: Prüft auf neue Nachrichten
async function checkForNewMessages() {
    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();

        // Nur wenn sich die Anzahl der Nachrichten geändert hat, laden wir neu
        if (history.length > lastMessageCount) {
            chatBox.innerHTML = ''; // Box leeren
            history.forEach(msg => {
                const roleClass = msg.role === 'user' ? 'user' : 'bot';
                appendMessage(roleClass, msg.content);
            });
            lastMessageCount = history.length;
        }
    } catch (error) {
        console.error("Polling Fehler:", error);
    }
}

// 3. Nachricht senden
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    sendBtn.disabled = true;

    // Lokale Anzeige vorab (optional, da Polling es ohnehin laden würde)
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
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) throw new Error('Server-Fehler');

        // Nach dem Senden sofort prüfen, um die KI-Antwort direkt zu sehen
        await checkForNewMessages();

    } catch (error) {
        appendMessage('bot', 'Fehler: Verbindung zum Server fehlgeschlagen.');
    } finally {
        if (chatBox.contains(loadingDiv)) chatBox.removeChild(loadingDiv);
        isProcessing = false;
        sendBtn.disabled = false;
        userInput.focus();
    }
}

sendBtn.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});

// INITIALISIERUNG
// Beim Starten den Verlauf laden
window.onload = checkForNewMessages;

// ALLE 3 SEKUNDEN auf neue Nachrichten prüfen (Echtzeit-Effekt)
setInterval(checkForNewMessages, 3000);