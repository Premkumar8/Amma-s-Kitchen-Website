class AmmaChatbot {
    constructor() {
        this.sessionId = this.generateSessionId();
        this.messages = [];
        this.isLoading = false;
        
        // Wait for DOM to be fully loaded
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => this.init());
        } else {
            this.init();
        }
    }

    init() {
        this.initElements();
        if(!this.widget) return; // Guard clause if elements missing
        this.attachEventListeners();
        this.showWelcomeMessage();
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9);
    }

    initElements() {
        this.widget = document.getElementById('chatbot-widget');
        this.toggleBtn = document.getElementById('chatbot-toggle');
        this.minimizeBtn = document.getElementById('minimize-btn');
        this.chatInput = document.getElementById('chat-input');
        this.sendBtn = document.getElementById('send-btn');
        this.messagesContainer = document.getElementById('chat-messages');
    }

    attachEventListeners() {
        this.toggleBtn.addEventListener('click', () => this.toggleChat());
        this.minimizeBtn.addEventListener('click', () => this.minimizeChat());
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        this.chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    toggleChat() {
        const isHidden = this.widget.classList.contains('hidden');
        if (isHidden) {
            this.widget.classList.remove('hidden');
            // Animate entrance
            this.widget.style.animation = 'none';
            this.widget.offsetHeight; /* trigger reflow */
            this.widget.style.animation = null; 
            setTimeout(() => this.chatInput.focus(), 100);
        } else {
            this.widget.classList.add('hidden');
        }
    }

    minimizeChat() {
        this.widget.classList.add('hidden');
    }

    // Helper to format time nicely (e.g. 10:30 AM)
    getFormattedTime() {
        return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    showWelcomeMessage() {
        // Only show if empty (prevents double welcome on re-renders if you expand functionality)
        if (this.messagesContainer.children.length === 0) {
            const welcomeMsg = {
                text: "Vanakam! 🙏 I am Amma's AI Assistant.<br>Ask me about our Sambar Powder, Ghee, or today's specials!",
                sender: 'amma',
                time: this.getFormattedTime()
            };
            this.renderMessage(welcomeMsg);
        }
    }

    async sendMessage() {
        const messageText = this.chatInput.value.trim();
        if (!messageText || this.isLoading) return;

        // 1. Add User Message
        const userMsg = {
            text: messageText,
            sender: 'user',
            time: this.getFormattedTime()
        };
        this.renderMessage(userMsg);
        this.chatInput.value = '';

        // 2. Show Typing Indicator
        this.isLoading = true;
        this.showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: messageText,
                    session_id: this.sessionId
                })
            });

            if (!response.ok) throw new Error('Network error');

            const data = await response.json();
            
            // Artificial delay (optional) to make it feel more natural if API is too fast
            // await new Promise(r => setTimeout(r, 500)); 

            this.removeTypingIndicator();

            // 3. Add Bot Message
            const botMsg = {
                text: data.message,
                sender: 'amma',
                time: this.getFormattedTime()
            };
            this.renderMessage(botMsg);

        } catch (error) {
            console.error('Chat Error:', error);
            this.removeTypingIndicator();
            this.renderMessage({
                text: "My internet connection is a bit weak right now. Please try again!",
                sender: 'amma',
                time: this.getFormattedTime()
            });
        } finally {
            this.isLoading = false;
            this.chatInput.focus();
        }
    }

    renderMessage(msg) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `message ${msg.sender}`;
        
        // Check if text contains line breaks
        const formattedText = msg.text.replace(/\n/g, '<br>');

        msgDiv.innerHTML = `
            <div class="message-content">
                ${formattedText}
            </div>
            <div class="message-time">${msg.time}</div>
        `;
        
        this.messagesContainer.appendChild(msgDiv);
        this.scrollToBottom();
    }

    showTypingIndicator() {
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message amma typing-container';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <div class="message-content" style="background: var(--msg-bot-bg);">
                <div class="typing">
                    <span></span><span></span><span></span>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }

    removeTypingIndicator() {
        const el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
}

// Instantiate
new AmmaChatbot();