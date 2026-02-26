const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const imageInput = document.getElementById('image-input');
const uploadBtn = document.getElementById('upload-btn');

let isProcessing = false;
let lastHistoryJSON = "";

// Hilfsfunktion: XSS-Schutz für HTML-Injections
function escapeHTML(str) {
    return str.replace(/[&<>'"]/g,
        tag => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            "'": '&#39;',
            '"': '&quot;'
        }[tag])
    );
}

// 1. Funktion: Nachricht im Interface anzeigen
function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    const cssClass = (role === 'assistant' || role === 'bot') ? 'bot' : 'user';
    msgDiv.className = `message ${cssClass}`;

    if (text.startsWith("IMG_CONFIRM:")) {
        const content = text.replace("IMG_CONFIRM:", "");
        const [imageUrl, userText] = content.split("|");

        // userText muss escaped werden, da wir innerHTML verwenden
        const safeText = userText ? escapeHTML(userText) : '';

        msgDiv.innerHTML = `
            <div class="image-wrapper">
                <img src="${imageUrl}" class="chat-img" 
                     onclick="window.open('${imageUrl}', '_blank')"
                     onerror="this.src='https://via.placeholder.com/150?text=Bild+nicht+gefunden'">
                ${safeText ? `<p class="img-caption">${safeText}</p>` : ''}
            </div>
        `;
    } else {
        // innerText ist von Natur aus sicher vor XSS
        msgDiv.innerText = text;
    }

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 2. Echtzeit-Funktion: Sync mit der Datenbank
async function refreshChat() {
    if (isProcessing) return; // Nicht synchronisieren, während wir aktiv etwas senden (verhindert Flackern)

    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();

        const currentJSON = JSON.stringify(history);

        if (currentJSON !== lastHistoryJSON) {
            chatBox.innerHTML = '';
            history.forEach(msg => appendMessage(msg.role, msg.content));
            lastHistoryJSON = currentJSON;
        }
    } catch (error) {
        console.error("Fehler beim Abrufen der History:", error);
    }
}

// 3. BILD-UPLOAD
if (uploadBtn && imageInput) {
    uploadBtn.onclick = () => imageInput.click();

    imageInput.onchange = async () => {
        const file = imageInput.files[0];
        if (!file || isProcessing) return;

        isProcessing = true;
        const message = userInput.value.trim();
        userInput.value = ''; // Feld direkt leeren

        // Ladeindikator anzeigen
        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'message bot loading';
        loadingMsg.innerText = '🖼️ Bild wird analysiert...';
        chatBox.appendChild(loadingMsg);
        chatBox.scrollTop = chatBox.scrollHeight;

        const formData = new FormData();
        formData.append('file', file);
        formData.append('message', message);

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload fehlgeschlagen');
            lastHistoryJSON = ""; // Erzwingt kompletten Neuaufbau beim nächsten Sync
            await refreshChat();
        } catch (error) {
            appendMessage('bot', '⚠️ Fehler: Bild-Analyse fehlgeschlagen.');
            userInput.value = message; // Text bei Fehler zurückgeben
        } finally {
            if (chatBox.contains(loadingMsg)) loadingMsg.remove();
            isProcessing = false;
            imageInput.value = '';
        }
    };
}

// 4. TEXT-CHAT (Mit Optimistic UI)
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    userInput.value = '';

    // Optimistic UI: Eigene Nachricht sofort anzeigen
    appendMessage('user', message);

    // Ladeindikator für die KI
    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message bot loading';
    typingIndicator.innerText = 'Lumina tippt...';
    chatBox.appendChild(typingIndicator);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) throw new Error("Server Error");

        lastHistoryJSON = ""; // Erzwingt UI-Update
        await refreshChat();
    } catch (error) {
        appendMessage('bot', '⚠️ Fehler beim Senden der Nachricht.');
        userInput.value = message; // Nachricht bei Fehler zurück ins Eingabefeld
    } finally {
        if (chatBox.contains(typingIndicator)) typingIndicator.remove();
        isProcessing = false;
    }
}

// Event Listener
sendBtn.onclick = sendMessage;
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault(); // Verhindert Zeilenumbruch bei Enter
        sendMessage();
    }
});

// Init & Polling
setInterval(refreshChat, 2000);
window.onload = refreshChat;