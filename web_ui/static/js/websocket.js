/* ========================================================================
   JARVIS WebSocket Handler
   ======================================================================== */

class JarvisWebSocket {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000; // ms
        
        this.connect();
    }
    
    connect() {
        // Get the current protocol and host
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const socketUrl = `${protocol}//${window.location.hostname}:${window.location.port}`;
        
        console.log(`[WebSocket] Connecting to ${socketUrl}`);
        
        this.socket = io(socketUrl, {
            reconnection: true,
            reconnectionDelay: this.reconnectDelay,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: this.maxReconnectAttempts,
            transports: ['websocket', 'polling']
        });
        
        this.setupListeners();
    }
    
    setupListeners() {
        // Connection events
        this.socket.on('connect', () => {
            this.connected = true;
            this.reconnectAttempts = 0;
            console.log('[WebSocket] Connected');
            this.updateConnectionStatus(true);
        });
        
        this.socket.on('disconnect', (reason) => {
            this.connected = false;
            console.log(`[WebSocket] Disconnected: ${reason}`);
            this.updateConnectionStatus(false);
        });
        
        this.socket.on('connect_error', (error) => {
            console.error('[WebSocket] Connection error:', error);
        });
        
        // Message events
        this.socket.on('status', (data) => {
            console.log('[WebSocket] Status:', data);
            if (window.jarvisUI) {
                window.jarvisUI.handleStatus(data);
            }
        });
        
        this.socket.on('response', (data) => {
            console.log('[WebSocket] Response:', data);
            if (window.jarvisUI) {
                window.jarvisUI.handleResponse(data);
            }
        });
        
        this.socket.on('error', (data) => {
            console.error('[WebSocket] Error:', data);
            if (window.jarvisUI) {
                window.jarvisUI.handleError(data);
            }
        });
        
        this.socket.on('metrics', (data) => {
            if (window.jarvisUI) {
                window.jarvisUI.handleMetrics(data);
            }
        });
        
        this.socket.on('listening_status', (data) => {
            if (window.jarvisUI) {
                window.jarvisUI.updateListeningStatus(data);
            }
        });
        
        this.socket.on('tool_result', (data) => {
            console.log('[WebSocket] Tool result:', data);
            if (window.jarvisUI) {
                window.jarvisUI.addLog(`Tool executed: ${data.tool}`, 'success');
            }
        });
    }
    
    updateConnectionStatus(connected) {
        if (window.jarvisUI && window.jarvisUI.connStatus) {
            if (connected) {
                window.jarvisUI.connStatus.classList.add('online');
                window.jarvisUI.connStatus.textContent = 'ONLINE';
            } else {
                window.jarvisUI.connStatus.classList.remove('online');
                window.jarvisUI.connStatus.textContent = 'OFFLINE';
            }
        }
    }
    
    // Public methods to emit events
    emit(event, data) {
        if (this.socket && this.connected) {
            this.socket.emit(event, data);
        } else {
            console.warn(`[WebSocket] Not connected, cannot emit '${event}'`);
        }
    }
    
    on(event, callback) {
        if (this.socket) {
            this.socket.on(event, callback);
        }
    }
    
    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

// Create global WebSocket instance
window.jarvisSocket = new JarvisWebSocket();

console.log('[WebSocket] Handler initialized');
