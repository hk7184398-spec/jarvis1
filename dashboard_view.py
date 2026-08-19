"""
dashboard_view.py — Web-based "Dashboard" view for J.A.R.V.I.S.

Adds a second, switchable UI (alongside the existing radar/HUD view in
ui.py) styled after a Brahma-AI-Lite-like layout: greeting header, daily
brief / dev co-pilot cards, command bar, and a right-hand chat/activity
workspace — rendered as HTML/CSS/JS inside a QWebEngineView.

Wiring back into the existing Jarvis backend goes through MainWindow,
which already owns on_text_command / _dispatch_command / metrics /
logging. This module does not talk to the backend directly — it only
exposes Qt signals that MainWindow connects to, and public methods that
MainWindow calls to push updates (log lines, metrics, state) into the
page. This keeps the same single source of truth as the radar view.

Requires the `PyQt6-WebEngine` package (add to requirements.txt):
    pip install PyQt6-WebEngine
"""
from __future__ import annotations

import html
import json
import time

from PyQt6.QtCore import QObject, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWebEngineWidgets import QWebEngineView


# ----------------------------------------------------------------------
# JS <-> Python bridge
# ----------------------------------------------------------------------
class _Bridge(QObject):
    """Exposed to the page as `window.bridge` via QWebChannel."""

    command_sent = pyqtSignal(str)
    mic_toggled  = pyqtSignal()
    radar_requested = pyqtSignal()

    @pyqtSlot(str)
    def sendCommand(self, text: str):
        text = text.strip()
        if text:
            self.command_sent.emit(text)

    @pyqtSlot()
    def toggleMic(self):
        self.mic_toggled.emit()

    @pyqtSlot()
    def showRadar(self):
        self.radar_requested.emit()


def _esc_js(text: str) -> str:
    """Safely embed a Python string inside a JS string literal via JSON."""
    return json.dumps(text)


class DashboardView(QWebEngineView):
    """Drop-in widget: add to a QStackedWidget next to the existing HUD."""

    command_sent    = pyqtSignal(str)   # re-exported for MainWindow to connect to
    mic_toggled     = pyqtSignal()
    radar_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._bridge = _Bridge()
        self._bridge.command_sent.connect(self.command_sent)
        self._bridge.mic_toggled.connect(self.mic_toggled)
        self._bridge.radar_requested.connect(self.radar_requested)

        self._channel = QWebChannel(self.page())
        self._channel.registerObject("bridge", self._bridge)
        self.page().setWebChannel(self._channel)

        self.setHtml(_PAGE_HTML, baseUrl=QUrl("about:blank"))

        self._muted = False

    # -- push updates from MainWindow into the page -----------------
    def push_log(self, text: str):
        self.page().runJavaScript(f"jarvisAppendLog({_esc_js(text)});")

    def update_metrics(self, cpu: float, mem: float, net_str: str):
        self.page().runJavaScript(
            f"jarvisUpdateMetrics({cpu:.0f}, {mem:.0f}, {_esc_js(net_str)});"
        )

    def set_state(self, state: str):
        self.page().runJavaScript(f"jarvisSetState({_esc_js(state)});")

    def set_mic(self, active: bool):
        self._muted = not active
        self.page().runJavaScript(f"jarvisSetMic({'true' if active else 'false'});")

    def set_daily_brief(self, text: str):
        self.page().runJavaScript(f"jarvisSetBrief({_esc_js(text)});")

    def set_dev_copilot(self, text: str):
        self.page().runJavaScript(f"jarvisSetCopilot({_esc_js(text)});")


# ----------------------------------------------------------------------
# HTML / CSS / JS
# ----------------------------------------------------------------------
_PAGE_HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  :root {
    --bg:      #00060a;
    --panel:   #010d14;
    --panel2:  #010f18;
    --border:  #0d3347;
    --border-b:#1a5c7a;
    --pri:     #00d4ff;
    --pri-dim: #007a99;
    --acc:     #ff6b00;
    --acc2:    #ffcc00;
    --green:   #00ff88;
    --red:     #ff3355;
    --text:    #8ffcff;
    --text-dim:#3a8a9a;
    --text-med:#5ab8cc;
    --white:   #d8f8ff;
  }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: var(--bg);
    font-family: 'Courier New', monospace;
    color: var(--text);
    overflow: hidden;
  }
  #root { display: flex; flex-direction: column; height: 100%; }

  /* header */
  #hdr {
    height: 64px; flex: 0 0 auto;
    background: #000d14; border-bottom: 1px solid var(--border-b);
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 18px;
  }
  #hdr .greet { font-size: 18px; font-weight: bold; color: var(--white); }
  #hdr .sub   { font-size: 11px; color: var(--pri-dim); margin-top: 2px; }
  #hdr .status-line { font-size: 10px; color: var(--text-med); margin-top: 3px; }
  #hdr .online { color: var(--green); }
  #hdr .right  { text-align: right; }
  #hdr .clock  { font-size: 20px; color: var(--pri); font-weight: bold; }
  #hdr .date   { font-size: 10px; color: var(--text-dim); }
  #hdr .sys    { font-size: 10px; color: var(--text-med); margin-top: 2px; }
  #hdr .navbtn {
    background: transparent; border: 1px solid var(--border-b);
    color: var(--pri); font-family: inherit; font-size: 10px;
    padding: 6px 10px; border-radius: 3px; cursor: pointer; margin-left: 10px;
  }
  #hdr .navbtn:hover { background: var(--panel2); }

  /* body */
  #body { flex: 1 1 auto; display: flex; min-height: 0; }
  #center { flex: 1 1 auto; padding: 18px; overflow-y: auto; }
  #right  { width: 340px; flex: 0 0 auto; border-left: 1px solid var(--border);
            background: var(--panel); display: flex; flex-direction: column; padding: 10px; }

  .card {
    background: var(--panel2); border: 1px solid var(--border);
    border-radius: 6px; padding: 12px 14px; margin-bottom: 14px;
  }
  .card h3 {
    margin: 0 0 8px 0; font-size: 11px; letter-spacing: 1px;
    color: var(--acc); text-transform: uppercase;
  }
  .card p { margin: 0; font-size: 12px; line-height: 1.6; color: var(--text-med); }

  #ring-wrap { display: flex; justify-content: center; margin: 10px 0 20px 0; }
  #ring {
    width: 150px; height: 150px; border-radius: 50%;
    border: 2px solid var(--pri-dim);
    display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 30px rgba(0,212,255,0.15) inset;
    font-weight: bold; color: var(--pri); font-size: 13px; letter-spacing: 2px;
  }

  #inputbar {
    display: flex; gap: 8px; align-items: center; margin-top: 6px;
  }
  #cmdInput {
    flex: 1; background: var(--bg); border: 1px solid var(--border-b);
    color: var(--white); font-family: inherit; font-size: 12px;
    padding: 10px 12px; border-radius: 4px; outline: none;
  }
  #cmdInput:focus { border-color: var(--pri); }
  #sendBtn, #micBtn {
    background: var(--panel2); border: 1px solid var(--border-b);
    color: var(--pri); font-family: inherit; font-size: 13px;
    padding: 9px 12px; border-radius: 4px; cursor: pointer;
  }
  #sendBtn:hover, #micBtn:hover { background: var(--border); }
  #micBtn.active { color: var(--green); border-color: var(--green); }
  #micBtn.muted  { color: var(--red);   border-color: var(--red); }

  /* right panel */
  #right h4 {
    font-size: 10px; color: var(--text-med); letter-spacing: 1px;
    margin: 4px 0 8px 0; text-transform: uppercase;
  }
  #stats { display: flex; gap: 8px; margin-bottom: 10px; }
  .stat {
    flex: 1; background: var(--panel2); border: 1px solid var(--border);
    border-radius: 4px; padding: 6px 8px;
  }
  .stat .lbl { font-size: 9px; color: var(--text-dim); }
  .stat .val { font-size: 14px; color: var(--pri); font-weight: bold; }

  #log {
    flex: 1 1 auto; overflow-y: auto; border: 1px solid var(--border);
    border-radius: 4px; padding: 8px; background: var(--bg);
    font-size: 11px; line-height: 1.5;
  }
  #log .entry { margin-bottom: 6px; color: var(--text-med); }
  #log .entry .tag { color: var(--acc2); font-weight: bold; }
  #log .entry .time { float: right; color: var(--text-dim); font-size: 9px; }

  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-thumb { background: var(--border-b); border-radius: 3px; }
</style>
</head>
<body>
<div id="root">

  <div id="hdr">
    <div>
      <div class="greet" id="greetLbl">Good Evening</div>
      <div class="sub">J.A.R.V.I.S · Dashboard View</div>
      <div class="status-line"><span class="online" id="stateLbl">● ONLINE</span></div>
    </div>
    <div class="right">
      <div class="clock" id="clockLbl">--:--:--</div>
      <div class="date" id="dateLbl"></div>
      <div class="sys" id="sysLbl">CPU --% · MEM --%</div>
    </div>
    <button class="navbtn" onclick="bridge.showRadar()">◎ RADAR VIEW</button>
  </div>

  <div id="body">
    <div id="center">
      <div class="card">
        <h3>Daily Brief</h3>
        <p id="briefTxt">Standing by.</p>
      </div>
      <div class="card">
        <h3>Developer Co-Pilot</h3>
        <p id="copilotTxt">Idle.</p>
      </div>

      <div id="ring-wrap"><div id="ring">J.A.R.V.I.S</div></div>

      <div id="inputbar">
        <input id="cmdInput" type="text" placeholder="Ask Jarvis anything...">
        <button id="micBtn" class="active" onclick="onMicClick()">🎙</button>
        <button id="sendBtn" onclick="onSend()">➤</button>
      </div>
    </div>

    <div id="right">
      <h4>Chat + Task Workspace</h4>
      <div id="stats">
        <div class="stat"><div class="lbl">CPU</div><div class="val" id="cpuVal">--%</div></div>
        <div class="stat"><div class="lbl">MEM</div><div class="val" id="memVal">--%</div></div>
        <div class="stat"><div class="lbl">NET</div><div class="val" id="netVal">--</div></div>
      </div>
      <div id="log"></div>
    </div>
  </div>

</div>

<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<script>
  let bridge = null;
  new QWebChannel(qt.webChannelTransport, function(channel) {
    bridge = channel.objects.bridge;
  });

  function onSend() {
    const inp = document.getElementById('cmdInput');
    const txt = inp.value.trim();
    if (!txt || !bridge) return;
    // Log line comes back from Python (single source of truth, same as radar view)
    bridge.sendCommand(txt);
    inp.value = '';
  }
  document.getElementById('cmdInput').addEventListener('keydown', function(e) {
    if (e.key === 'Enter') onSend();
  });

  let micActive = true;
  function onMicClick() {
    if (bridge) bridge.toggleMic();
  }
  function jarvisSetMic(active) {
    micActive = active;
    const b = document.getElementById('micBtn');
    b.classList.toggle('active', active);
    b.classList.toggle('muted', !active);
    b.textContent = active ? '🎙' : '🔇';
  }

  function jarvisAppendLog(text) {
    const log = document.getElementById('log');
    const div = document.createElement('div');
    div.className = 'entry';
    const t = new Date();
    const ts = t.toTimeString().slice(0,5);
    div.innerHTML = '<span class="time">' + ts + '</span>' + escapeHtml(text);
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    while (log.children.length > 200) log.removeChild(log.firstChild);
  }

  function jarvisUpdateMetrics(cpu, mem, netStr) {
    document.getElementById('cpuVal').textContent = cpu + '%';
    document.getElementById('memVal').textContent = mem + '%';
    document.getElementById('netVal').textContent = netStr;
    document.getElementById('sysLbl').textContent = 'CPU ' + cpu + '% · MEM ' + mem + '%';
  }

  function jarvisSetState(state) {
    const el = document.getElementById('stateLbl');
    const map = {
      'LISTENING': ['● ONLINE', ''],
      'SPEAKING':  ['● SPEAKING', 'color:#ff6b00'],
      'MUTED':     ['● MUTED', 'color:#ff3355'],
      'THINKING':  ['● THINKING', 'color:#ffcc00'],
    };
    const [label, style] = map[state] || ['● ' + state, ''];
    el.textContent = label;
    el.setAttribute('style', style);
  }

  function jarvisSetBrief(text)   { document.getElementById('briefTxt').textContent = text; }
  function jarvisSetCopilot(text) { document.getElementById('copilotTxt').textContent = text; }

  function escapeHtml(s) {
    const d = document.createElement('div');
    d.innerText = s;
    return d.innerHTML;
  }

  function updateGreeting() {
    const h = new Date().getHours();
    const g = h < 12 ? 'Good Morning' : (h < 18 ? 'Good Afternoon' : 'Good Evening');
    document.getElementById('greetLbl').textContent = g;
    const now = new Date();
    document.getElementById('clockLbl').textContent = now.toTimeString().slice(0,8);
    document.getElementById('dateLbl').textContent =
      now.toDateString();
  }
  updateGreeting();
  setInterval(updateGreeting, 1000);
</script>
</body>
</html>
"""
