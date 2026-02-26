const chatBox = document.getElementById('chat-box');
const userInput = document.getElementById('user-input');
const sendBtn = document.getElementById('send-btn');
const imageInput = document.getElementById('image-input');
const uploadBtn = document.getElementById('upload-btn');

let isProcessing = false;
let lastHistoryJSON = "";

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

// NEU: smoothScroll Option
function appendMessage(role, text, smoothScroll = true) {
    const msgDiv = document.createElement('div');
    const cssClass = (role === 'assistant' || role === 'bot') ? 'bot' : 'user';
    msgDiv.className = `message ${cssClass}`;

    if (text.startsWith("IMG_CONFIRM:")) {
        const content = text.replace("IMG_CONFIRM:", "");
        const [imageUrl, userText] = content.split("|");
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
        msgDiv.innerText = text;
    }

    chatBox.appendChild(msgDiv);

    if (smoothScroll) {
        chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });
    }
}

async function refreshChat() {
    if (isProcessing) return;

    try {
        const response = await fetch('/history');
        if (!response.ok) return;
        const history = await response.json();

        const currentJSON = JSON.stringify(history);

        if (currentJSON !== lastHistoryJSON) {
            chatBox.innerHTML = '';
            // False = Blockiert die Animation beim Laden
            history.forEach(msg => appendMessage(msg.role, msg.content, false));
            lastHistoryJSON = currentJSON;

            // Einmaliger harter Sprung ans Ende ohne Animation
            chatBox.scrollTop = chatBox.scrollHeight;
        }
    } catch (error) {
        console.error("Fehler beim Abrufen der History:", error);
    }
}

if (uploadBtn && imageInput) {
    uploadBtn.onclick = () => imageInput.click();

    imageInput.onchange = async () => {
        const file = imageInput.files[0];
        if (!file || isProcessing) return;

        isProcessing = true;
        const message = userInput.value.trim();
        userInput.value = '';

        const loadingMsg = document.createElement('div');
        loadingMsg.className = 'message bot loading';
        loadingMsg.innerText = '🖼️ Bild wird analysiert...';
        chatBox.appendChild(loadingMsg);
        chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });

        const formData = new FormData();
        formData.append('file', file);
        formData.append('message', message);

        try {
            const response = await fetch('/upload', { method: 'POST', body: formData });
            if (!response.ok) throw new Error('Upload fehlgeschlagen');
            lastHistoryJSON = "";
            await refreshChat();
        } catch (error) {
            appendMessage('bot', '⚠️ Fehler: Bild-Analyse fehlgeschlagen.');
            userInput.value = message;
        } finally {
            if (chatBox.contains(loadingMsg)) loadingMsg.remove();
            isProcessing = false;
            imageInput.value = '';
        }
    };
}

async function sendMessage() {
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    isProcessing = true;
    userInput.value = '';

    appendMessage('user', message, true);

    const typingIndicator = document.createElement('div');
    typingIndicator.className = 'message bot loading';
    typingIndicator.innerText = 'Lumina tippt...';
    chatBox.appendChild(typingIndicator);
    chatBox.scrollTo({ top: chatBox.scrollHeight, behavior: 'smooth' });

    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) throw new Error("Server Error");

        lastHistoryJSON = "";
        await refreshChat();
    } catch (error) {
        appendMessage('bot', '⚠️ Fehler beim Senden der Nachricht.');
        userInput.value = message;
    } finally {
        if (chatBox.contains(typingIndicator)) typingIndicator.remove();
        isProcessing = false;
    }
}

sendBtn.onclick = sendMessage;
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

setInterval(refreshChat, 2000);
window.onload = refreshChat;