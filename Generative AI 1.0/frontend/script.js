const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const imageInput = document.getElementById('image-input');
const uploadBtn = document.getElementById('upload-btn');

let isProcessing = false;
let lastHistoryJSON = ""; // Speichert den exakten Inhalt, um Änderungen sofort zu erkennen

// 1. Funktion: Nachricht im Interface anzeigen
function appendMessage(role, text) {
    const msgDiv = document.createElement('div');
    const cssClass = (role === 'assistant' || role === 'bot') ? 'bot' : 'user';
    msgDiv.className = `message ${cssClass}`;

    if (text.startsWith("IMG_CONFIRM:")) {
        const content = text.replace("IMG_CONFIRM:", "");
        const [imageUrl, userText] = content.split("|");

        msgDiv.innerHTML = `
            <div class="image-wrapper">
                <img src="${imageUrl}" class="chat-img" 
                     onclick="window.open('${imageUrl}', '_blank')"
                     onerror="this.src='https://via.placeholder.com/150?text=Bild+nicht+gefunden'">
                ${userText ? `<p class="img-caption">${userText}</p>` : ''}
            </div>
        `;
    } else {
        msgDiv.innerText = text;
    }

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

// 2. Echtzeit-Funktion: Zieht den exakten Chatverlauf aus der Datenbank (Sync mit Telegram)
async function refreshChat() {
    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();

        // Vergleicht den gesamten Text der Historie, nicht nur die Anzahl
        const currentJSON = JSON.stringify(history);

        if (currentJSON !== lastHistoryJSON) {
            chatBox.innerHTML = ''; // Box komplett leeren
            history.forEach(msg => {
                appendMessage(msg.role, msg.content);
            });
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
            await refreshChat(); // Sofort nach Upload aktualisieren
        } catch (error) {
            appendMessage('bot', 'Fehler: Bild-Analyse fehlgeschlagen.');
        } finally {
            if (chatBox.contains(loadingMsg)) chatBox.removeChild(loadingMsg);
            isProcessing = false;
            imageInput.value = '';
            userInput.value = '';
        }
    };
}

// 4. TEXT-CHAT
async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    userInput.value = '';

    // Die Nachricht wird an den Server gesendet. 
    // refreshChat() holt sie sich danach sofort aus der DB, 
    // damit Web und Telegram die 100% gleiche Reihenfolge haben.
    try {
        await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });
        await refreshChat();
    } catch (error) {
        appendMessage('bot', 'Fehler beim Senden.');
    } finally {
        isProcessing = false;
    }
}

sendBtn.onclick = sendMessage;
userInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

// Schneller Takt für das Echtzeit-Gefühl mit Telegram (alle 2 Sekunden)
setInterval(refreshChat, 2000);
window.onload = refreshChat;