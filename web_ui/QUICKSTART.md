# JARVIS Web UI - Quick Start (5 minutes)

## ⚡ TL;DR

```bash
# 1. Enter web folder
cd web_ui

# 2. Run (Linux/Mac)
./run.sh

# 2. Run (Windows)
run.bat

# 3. Open browser
http://localhost:5000

# 4. Enter API keys when prompted
```

---

## 📋 Step-by-Step

### Step 1: Get API Keys

**Gemini API Key:**
- Go to https://aistudio.google.com/apikey
- Create new API key
- Copy the key

**OpenRouter API Key:**
- Go to https://openrouter.ai/keys
- Create new key (free tier available)
- Copy the key

### Step 2: Start Server

**Linux / macOS:**
```bash
cd web_ui
./run.sh
```

**Windows:**
```bash
cd web_ui
run.bat
```

**Output should show:**
```
╔════════════════════════════════════════════════════════════════╗
║           J.A.R.V.I.S. WEB SERVER STARTUP                     ║
╚════════════════════════════════════════════════════════════════╝

🚀 Starting on http://localhost:5000
📡 WebSocket enabled for real-time communication
🔧 Integrating with existing jarvis1 backend
```

### Step 3: Open Web UI

In your browser:
```
http://localhost:5000
```

You should see:
- Dark interface with cyan/orange theme
- Initialize modal asking for API keys
- Three-panel layout (left: status, center: HUD, right: interaction)

### Step 4: Initialize

1. Paste Gemini API Key
2. Paste OpenRouter API Key
3. Click "Initialize"
4. Wait for "JARVIS initialized successfully" message

### Step 5: Start Using

**Try these commands:**
- "What time is it?"
- "Show my memory"
- "What is the weather like?"
- "Execute the trading signals skill"

---

## 🎯 First Commands to Try

```
User: Hello, who are you?
JARVIS: I am JARVIS, Tony Stark's AI assistant. How can I help you?

User: What can you do?
JARVIS: I can help with [lists tools/skills]

User: Show system status
JARVIS: [CPU/Memory/Disk metrics displayed]

User: What is my current memory?
JARVIS: [Event context displayed]
```

---

## 🔧 Troubleshooting

### "Python not found"
```bash
python3 --version  # Check installation
# If not installed: https://python.org/downloads
```

### "Permission denied: run.sh"
```bash
chmod +x run.sh
./run.sh
```

### "Port 5000 already in use"
```bash
./run.sh 8000  # Use port 8000 instead
# Then open: http://localhost:8000
```

### "WebSocket connection failed"
1. Check Flask is running (should see output in terminal)
2. Try refreshing browser
3. Check firewall settings

### "API key invalid"
1. Double-check key was copied fully
2. Make sure you used correct key (Gemini ≠ OpenRouter)
3. Check key isn't expired (regenerate if needed)

---

## 🌐 Next Steps

### Deploy to Domain

Once happy with localhost:

1. Buy a domain (Namecheap, GoDaddy, etc.)
2. Get a server (DigitalOcean, AWS, etc.)
3. SSH into server and run startup script
4. Point domain DNS to server IP

See README.md for full deployment guide.

### Customize

- Modify colors in `static/css/style.css` (`:root` section)
- Add new buttons in `templates/index.html`
- Add new event handlers in `static/js/main.js`
- Add tools in parent `jarvis1/actions/` folder

### Integrate Tools

Edit `app.py` to add custom tools:

```python
@socketio.on('my_tool')
def handle_my_tool(data):
    result = my_custom_function(data)
    emit('tool_result', {'tool': 'my_tool', 'result': result})
```

Then call from UI:
```javascript
window.jarvisSocket.emit('my_tool', { param: 'value' });
```

---

## 📚 Documentation

- **Full Readme:** `README.md`
- **API Reference:** See "API Endpoints" in README.md
- **Architecture:** See "Architecture" in README.md
- **Deployment:** See "Domain Deployment" in README.md

---

## ✅ Checklist

- [ ] Python 3.8+ installed
- [ ] API keys obtained (Gemini + OpenRouter)
- [ ] run.sh / run.bat works
- [ ] Browser opens http://localhost:5000
- [ ] API keys entered in modal
- [ ] "JARVIS initialized successfully" message seen
- [ ] Can send messages and get responses
- [ ] Radar HUD and metrics update in real-time

**All checked? You're ready to go!** 🚀

---

## 💬 Need Help?

1. Check README.md for detailed docs
2. See troubleshooting section above
3. Check Flask terminal output for error messages
4. Open GitHub issue: https://github.com/hk7184398-spec/jarvis1/issues

**Happy coding!** ✨
