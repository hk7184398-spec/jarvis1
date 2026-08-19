#!/usr/bin/env python3
"""
JARVIS1 Web UI - Flask + WebSocket Server
Mirrors PyQt6 UI + real backend (Gemini Live, OpenRouter, tools)
"""

import asyncio
import threading
import json
import time
import os
import sys
from pathlib import Path
from functools import wraps
from datetime import datetime

import psutil
from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import check_password_hash, generate_password_hash

# Add parent repo to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config import get_gemini_key, get_openrouter_key
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
    should_extract_memory, extract_memory
)
from or_client import OpenRouterClient

# System prompt loader
def _load_system_prompt():
    try:
        from core.paths import PROMPT_PATH
        return PROMPT_PATH.read_text(encoding='utf-8')
    except:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'jarvis-web-secret-key-change-in-production')
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# ============================================================================
# GLOBAL STATE
# ============================================================================

class JarvisWebState:
    def __init__(self):
        self.is_listening = False
        self.memory = load_memory()
        self.system_metrics = self._get_system_metrics()
        self.or_client = OpenRouterClient()
        self.active_sessions = {}
        self.tool_history = []
        
    def _get_system_metrics(self):
        return {
            'cpu': psutil.cpu_percent(interval=0.1),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'timestamp': datetime.now().isoformat()
        }
    
    def update_metrics(self):
        self.system_metrics = self._get_system_metrics()
        return self.system_metrics

jarvis_state = JarvisWebState()

# ============================================================================
# AUTHENTICATION (OPTIONAL - for local use)
# ============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve main UI"""
    return render_template('index.html')

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get JARVIS system status"""
    metrics = jarvis_state.update_metrics()
    return jsonify({
        'status': 'online',
        'listening': jarvis_state.is_listening,
        'metrics': metrics,
        'memory_loaded': len(jarvis_state.memory.get('events', [])),
        'sessions': len(jarvis_state.active_sessions)
    })

@app.route('/api/memory', methods=['GET'])
def get_memory():
    """Get formatted memory for context"""
    formatted = format_memory_for_prompt(jarvis_state.memory, max_chars=4000)
    return jsonify({
        'memory': formatted,
        'event_count': len(jarvis_state.memory.get('events', [])),
        'raw': jarvis_state.memory
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """Get recent tool execution history"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify({
        'history': jarvis_state.tool_history[-limit:],
        'total': len(jarvis_state.tool_history)
    })

@app.route('/api/init', methods=['POST'])
def init_jarvis():
    """Initialize JARVIS with API keys"""
    data = request.get_json()
    
    gemini_key = data.get('gemini_key')
    or_key = data.get('openrouter_key')
    
    if not gemini_key or not or_key:
        return jsonify({'error': 'Missing API keys'}), 400
    
    # Store in environment (or config file)
    os.environ['GEMINI_API_KEY'] = gemini_key
    os.environ['OPENROUTER_API_KEY'] = or_key
    
    # Reinit clients
    jarvis_state.or_client = OpenRouterClient()
    
    session['initialized'] = True
    session['user_id'] = 'web_user'
    
    return jsonify({'success': True, 'message': 'JARVIS initialized'})

# ============================================================================
# WEBSOCKET EVENTS
# ============================================================================

@socketio.on('connect')
def handle_connect():
    """Client connected"""
    print(f"[WEB] Client connected: {request.sid}")
    emit('status', {'message': 'Connected to JARVIS', 'type': 'success'})

@socketio.on('disconnect')
def handle_disconnect():
    """Client disconnected"""
    sid = request.sid
    if sid in jarvis_state.active_sessions:
        del jarvis_state.active_sessions[sid]
    print(f"[WEB] Client disconnected: {sid}")

@socketio.on('request_message')
def handle_message(data):
    """Handle user message"""
    sid = request.sid
    user_msg = data.get('message', '').strip()
    
    if not user_msg:
        emit('error', {'message': 'Empty message'})
        return
    
    emit('status', {'message': f'Processing: {user_msg[:50]}...', 'type': 'info'})
    
    # Log message
    print(f"[WEB] User message: {user_msg}")
    
    # Prepare context
    memory_context = format_memory_for_prompt(jarvis_state.memory, max_chars=2000)
    system_prompt = _load_system_prompt()
    
    # Call OR client (threaded to not block)
    def process():
        try:
            response = jarvis_state.or_client.query(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{memory_context}\n\n{user_msg}"}
                ],
                max_tokens=1024,
                temperature=0.7
            )
            
            if response['success']:
                assistant_msg = response['message']
                
                # Update memory if needed
                if should_extract_memory(user_msg, assistant_msg):
                    try:
                        extracted = extract_memory(user_msg, assistant_msg)
                        if extracted:
                            update_memory(jarvis_state.memory, extracted)
                    except:
                        pass
                
                # Emit response
                emit('response', {
                    'message': assistant_msg,
                    'model': response.get('model', 'unknown'),
                    'tokens': response.get('tokens', 0),
                    'type': 'text'
                })
            else:
                emit('error', {'message': response.get('error', 'Unknown error')})
        except Exception as e:
            emit('error', {'message': f'Error: {str(e)}'})
    
    threading.Thread(target=process, daemon=True).start()

@socketio.on('start_listening')
def handle_start_listening():
    """Start Gemini Live listening (if available)"""
    jarvis_state.is_listening = True
    emit('status', {
        'message': 'Listening started',
        'type': 'info'
    })
    socketio.emit('listening_status', {'listening': True}, broadcast=True)

@socketio.on('stop_listening')
def handle_stop_listening():
    """Stop Gemini Live listening"""
    jarvis_state.is_listening = False
    emit('status', {
        'message': 'Listening stopped',
        'type': 'info'
    })
    socketio.emit('listening_status', {'listening': False}, broadcast=True)

@socketio.on('get_metrics')
def handle_get_metrics():
    """Stream system metrics"""
    metrics = jarvis_state.update_metrics()
    emit('metrics', metrics)

@socketio.on('execute_tool')
def handle_execute_tool(data):
    """Execute a tool action"""
    tool_name = data.get('tool')
    params = data.get('params', {})
    
    if not tool_name:
        emit('error', {'message': 'No tool specified'})
        return
    
    emit('status', {'message': f'Executing: {tool_name}', 'type': 'info'})
    
    def execute():
        try:
            # Mock tool execution for now (integrate with actual tools later)
            result = f"Tool '{tool_name}' executed with params: {params}"
            
            # Log to history
            jarvis_state.tool_history.append({
                'tool': tool_name,
                'params': params,
                'result': result,
                'timestamp': datetime.now().isoformat(),
                'success': True
            })
            
            emit('tool_result', {
                'tool': tool_name,
                'result': result,
                'type': 'success'
            })
        except Exception as e:
            jarvis_state.tool_history.append({
                'tool': tool_name,
                'params': params,
                'error': str(e),
                'timestamp': datetime.now().isoformat(),
                'success': False
            })
            emit('error', {'message': f'Tool error: {str(e)}'})
    
    threading.Thread(target=execute, daemon=True).start()

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Server error'}), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║           J.A.R.V.I.S. WEB INTERFACE - LOCALHOST              ║
    ╚════════════════════════════════════════════════════════════════╝
    
    🚀 Starting on http://localhost:5000
    📡 WebSocket enabled for real-time communication
    🔧 Integrating with existing jarvis1 backend
    
    """)
    
    socketio.run(
        app,
        host='0.0.0.0',
        port=5000,
        debug=True,
        allow_unsafe_werkzeug=True
    )
