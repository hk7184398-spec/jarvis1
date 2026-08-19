/* ========================================================================
   JARVIS WEB UI - Main JavaScript
   ======================================================================== */

class JarvisUI {
    constructor() {
        this.isInitialized = false;
        this.isListening = false;
        this.metrics = {};
        
        this.initElements();
        this.attachEventListeners();
        this.checkInitialization();
        this.startMetricsUpdate();
        this.startClockUpdate();
    }
    
    initElements() {
        // Header
        this.listeningIndicator = document.getElementById('listening-indicator');
        
        // Left panel
        this.cpuMeter = document.getElementById('cpu-meter');
        this.cpuValue = document.getElementById('cpu-value');
        this.memMeter = document.getElementById('mem-meter');
        this.memValue = document.getElementById('mem-value');
        this.diskMeter = document.getElementById('disk-meter');
        this.diskValue = document.getElementById('disk-value');
        this.connStatus = document.getElementById('conn-status');
        this.memLoaded = document.getElementById('mem-loaded');
        this.sessionCount = document.getElementById('sessions-count');
        
        // Center
        this.radarCanvas = document.getElementById('radar-canvas');
        this.logContent = document.getElementById('log-content');
        
        // Right panel
        this.messageInput = document.getElementById('message-input');
        this.sendBtn = document.getElementById('send-btn');
        this.responseBox = document.getElementById('response-box');
        
        // Buttons
        this.voiceBtn = document.getElementById('voice-btn');
        this.listenBtn = document.getElementById('listen-btn');
        this.settingsBtn = document.getElementById('settings-btn');
        this.menuBtn = document.getElementById('menu-btn');
        this.quickBtns = document.querySelectorAll('.quick-btn');
        
        // Modal
        this.initModal = document.getElementById('init-modal');
        this.geminiKeyInput = document.getElementById('gemini-key-input');
        this.openrouterKeyInput = document.getElementById('openrouter-key-input');
        this.initConfirmBtn = document.getElementById('init-confirm');
        this.initCancelBtn = document.getElementById('init-cancel');
        
        // Footer
        this.gitInfo = document.getElementById('git-info');
        this.modelInfo = document.getElementById('model-info');
        this.timestamp = document.getElementById('timestamp');
    }
    
    attachEventListeners() {
        // Message sending
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Voice/Listen
        this.voiceBtn.addEventListener('click', () => this.toggleVoice());
        this.listenBtn.addEventListener('click', () => this.toggleListening());
        
        // Settings
        this.settingsBtn.addEventListener('click', () => this.showSettings());
        this.menuBtn.addEventListener('click', () => this.showMenu());
        
        // Quick actions
        this.quickBtns.forEach(btn => {
            btn.addEventListener('click', () => this.executeQuickAction(btn.dataset.tool));
        });
        
        // Modal
        this.initConfirmBtn.addEventListener('click', () => this.initializeJarvis());
        this.initCancelBtn.addEventListener('click', () => this.closeInitModal());
        
        // WebSocket events
        if (window.jarvisSocket) {
            window.jarvisSocket.on('status', (data) => this.handleStatus(data));
            window.jarvisSocket.on('response', (data) => this.handleResponse(data));
            window.jarvisSocket.on('error', (data) => this.handleError(data));
            window.jarvisSocket.on('metrics', (data) => this.handleMetrics(data));
            window.jarvisSocket.on('listening_status', (data) => this.updateListeningStatus(data));
        }
    }
    
    checkInitialization() {
        // Check if already initialized
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                if (data.listening !== undefined) {
                    this.isInitialized = true;
                    this.updateMetrics(data.metrics);
                } else {
                    this.showInitModal();
                }
            })
            .catch(() => this.showInitModal());
    }
    
    showInitModal() {
        this.initModal.classList.add('active');
    }
    
    closeInitModal() {
        this.initModal.classList.remove('active');
    }
    
    initializeJarvis() {
        const geminiKey = this.geminiKeyInput.value.trim();
        const openrouterKey = this.openrouterKeyInput.value.trim();
        
        if (!geminiKey || !openrouterKey) {
            this.addLog('Both API keys are required', 'error');
            return;
        }
        
        fetch('/api/init', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gemini_key: geminiKey,
                openrouter_key: openrouterKey
            })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                this.isInitialized = true;
                this.closeInitModal();
                this.addLog('JARVIS initialized successfully', 'success');
                
                // Connect to WebSocket
                if (window.jarvisSocket) {
                    window.jarvisSocket.emit('request_message', {
                        message: 'Hello, I am ready to assist.'
                    });
                }
            } else {
                this.addLog(data.error, 'error');
            }
        })
        .catch(err => {
            this.addLog(`Initialization error: ${err}`, 'error');
        });
    }
    
    sendMessage() {
        const message = this.messageInput.value.trim();
        
        if (!message) {
            return;
        }
        
        // Clear input
        this.messageInput.value = '';
        
        // Add to log
        this.addLog(`> ${message}`, 'info');
        
        // Send via WebSocket
        if (window.jarvisSocket) {
            window.jarvisSocket.emit('request_message', { message });
        } else {
            this.addLog('Not connected to JARVIS', 'error');
        }
    }
    
    handleStatus(data) {
        this.addLog(data.message, data.type || 'info');
    }
    
    handleResponse(data) {
        this.responseBox.innerHTML = `
            <div style="color: var(--green); margin-bottom: 8px;">
                [${data.model}] ${data.tokens} tokens
            </div>
            <div>${this.escapeHtml(data.message)}</div>
        `;
        this.addLog(data.message.substring(0, 100), 'success');
    }
    
    handleError(data) {
        this.addLog(data.message, 'error');
        this.responseBox.innerHTML = `<div style="color: var(--red);">${this.escapeHtml(data.message)}</div>`;
    }
    
    handleMetrics(data) {
        this.updateMetrics(data);
    }
    
    updateMetrics(metrics) {
        if (!metrics) return;
        
        // CPU
        if (metrics.cpu !== undefined) {
            const cpu = Math.min(metrics.cpu, 100);
            this.cpuMeter.style.width = cpu + '%';
            this.cpuValue.textContent = cpu.toFixed(1) + '%';
        }
        
        // Memory
        if (metrics.memory !== undefined) {
            const mem = Math.min(metrics.memory, 100);
            this.memMeter.style.width = mem + '%';
            this.memValue.textContent = mem.toFixed(1) + '%';
        }
        
        // Disk
        if (metrics.disk !== undefined) {
            const disk = Math.min(metrics.disk, 100);
            this.diskMeter.style.width = disk + '%';
            this.diskValue.textContent = disk.toFixed(1) + '%';
        }
        
        this.metrics = metrics;
    }
    
    toggleVoice() {
        // Toggle voice recording
        if (!this.isInitialized) {
            this.addLog('JARVIS not initialized', 'error');
            return;
        }
        
        if (window.jarvisSocket) {
            if (this.voiceBtn.classList.contains('active')) {
                window.jarvisSocket.emit('stop_listening');
                this.voiceBtn.classList.remove('active');
            } else {
                window.jarvisSocket.emit('start_listening');
                this.voiceBtn.classList.add('active');
            }
        }
    }
    
    toggleListening() {
        if (this.isListening) {
            if (window.jarvisSocket) {
                window.jarvisSocket.emit('stop_listening');
            }
            this.isListening = false;
            this.listenBtn.classList.remove('active');
        } else {
            if (window.jarvisSocket) {
                window.jarvisSocket.emit('start_listening');
            }
            this.isListening = true;
            this.listenBtn.classList.add('active');
        }
    }
    
    updateListeningStatus(data) {
        this.isListening = data.listening;
        const indicator = this.listeningIndicator;
        
        if (data.listening) {
            indicator.classList.add('active');
            indicator.querySelector('span').textContent = 'LISTENING';
        } else {
            indicator.classList.remove('active');
            indicator.querySelector('span').textContent = 'STANDBY';
        }
    }
    
    executeQuickAction(tool) {
        const actions = {
            weather: 'What is the current weather?',
            time: 'What time is it?',
            memory: 'Show my memory/events',
            status: 'Show system status'
        };
        
        const message = actions[tool] || `Execute ${tool}`;
        this.messageInput.value = message;
        this.sendMessage();
    }
    
    addLog(message, type = 'info') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${this.getTime()}] ${message}`;
        
        this.logContent.appendChild(entry);
        this.logContent.scrollTop = this.logContent.scrollHeight;
        
        // Keep log size manageable
        while (this.logContent.children.length > 100) {
            this.logContent.removeChild(this.logContent.firstChild);
        }
    }
    
    showSettings() {
        this.addLog('Settings dialog not yet implemented', 'warning');
    }
    
    showMenu() {
        this.addLog('Menu not yet implemented', 'warning');
    }
    
    startMetricsUpdate() {
        setInterval(() => {
            if (window.jarvisSocket && this.isInitialized) {
                window.jarvisSocket.emit('get_metrics');
            }
        }, 1500);
    }
    
    startClockUpdate() {
        setInterval(() => {
            const now = new Date();
            this.timestamp.textContent = now.toLocaleTimeString('en-US', {
                hour12: false,
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }, 1000);
    }
    
    getTime() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', {
            hour12: false,
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.jarvisUI = new JarvisUI();
    console.log('JARVIS UI initialized');
});
