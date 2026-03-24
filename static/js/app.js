/**
 * GitHub Copilot CLI Tutorials — frontend
 * Handles: xterm.js terminal, Socket.IO, file explorer, restore
 */

(function () {
  'use strict';

  // -----------------------------------------------------------------------
  // Toast notifications
  // -----------------------------------------------------------------------

  /** Singleton container for toast notification elements */
  const toastContainer = (() => {
    const el = document.createElement('div');
    el.className = 'toast-container';
    document.body.appendChild(el);
    return el;
  })();

  function showToast(message, type = 'info', duration = 3000) {
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    toastContainer.appendChild(el);
    setTimeout(() => el.remove(), duration);
  }

  // -----------------------------------------------------------------------
  // Tab switching
  // -----------------------------------------------------------------------
  window.showTab = function (name) {
    document.querySelectorAll('.workspace-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));

    const tab = document.getElementById('workspace-' + name);
    const btn = document.getElementById('tab-' + name);
    if (tab) tab.classList.add('active');
    if (btn) btn.classList.add('active');

    if (name === 'terminal') {
      fitAddon && fitAddon.fit();
    }
  };

  // -----------------------------------------------------------------------
  // ANSI terminal color helpers
  // -----------------------------------------------------------------------
  const ANSI = {
    RESET:  '\x1b[0m',
    YELLOW: '\x1b[33m',
    RED:    '\x1b[31m',
    GREEN:  '\x1b[32m',
  };

  // -----------------------------------------------------------------------
  // Terminal setup
  // -----------------------------------------------------------------------
  let term, fitAddon, socket;

  function initTerminal() {
    const container = document.getElementById('terminal-container');
    if (!container) return;

    term = new Terminal({
      cursorBlink: true,
      fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace",
      fontSize: 14,
      lineHeight: 1.4,
      theme: {
        background:   '#1e1e1e',
        foreground:   '#d4d4d4',
        cursor:       '#aeafad',
        selectionBackground: 'rgba(88,166,255,0.3)',
        black:   '#1e1e1e', red:     '#f44747',
        green:   '#6a9955', yellow:  '#d7ba7d',
        blue:    '#569cd6', magenta: '#c678dd',
        cyan:    '#56b6c2', white:   '#d4d4d4',
        brightBlack:   '#808080', brightRed:     '#f44747',
        brightGreen:   '#6a9955', brightYellow:  '#d7ba7d',
        brightBlue:    '#79c0ff', brightMagenta: '#bc8cff',
        brightCyan:    '#56b6c2', brightWhite:   '#e6edf3',
      },
      scrollback: 5000,
    });

    fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);
    term.open(container);
    fitAddon.fit();

    // Resize observer
    const observer = new ResizeObserver(() => fitAddon && fitAddon.fit());
    observer.observe(container);

    // Socket.IO connection
    socket = io({ transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
      socket.emit('start_terminal', {
        challenge_id: CHALLENGE_ID,
        session_id: SESSION_ID,
      });
    });

    socket.on('output', data => {
      term.write(data.data);
    });

    socket.on('terminal_closed', () => {
      term.write(`\r\n${ANSI.YELLOW}[Terminal session ended. Refresh the page to start a new one.]${ANSI.RESET}\r\n`);
    });

    socket.on('error', data => {
      term.write(`\r\n${ANSI.RED}[Error: ${data.message || 'unknown'}]${ANSI.RESET}\r\n`);
    });

    socket.on('disconnect', () => {
      term.write(`\r\n${ANSI.YELLOW}[Disconnected from server]${ANSI.RESET}\r\n`);
    });

    // Forward key input
    term.onData(data => {
      if (socket && socket.connected) {
        socket.emit('input', { data });
      }
    });

    // Forward terminal resize
    term.onResize(({ rows, cols }) => {
      if (socket && socket.connected) {
        socket.emit('resize', { rows, cols });
      }
    });
  }

  // -----------------------------------------------------------------------
  // File explorer
  // -----------------------------------------------------------------------
  window.loadFile = function (filename) {
    // Update active state
    document.querySelectorAll('.file-item').forEach(el => {
      el.classList.toggle('active', el.dataset.filename === filename);
    });

    const nameEl = document.getElementById('file-viewer-name');
    const contentEl = document.getElementById('file-viewer-content');

    nameEl.textContent = '⏳ Loading ' + filename + ' …';
    contentEl.innerHTML = '';

    fetch(`/api/challenge/${encodeURIComponent(CHALLENGE_ID)}/file?name=${encodeURIComponent(filename)}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          nameEl.textContent = filename + ' (error)';
          contentEl.textContent = data.error;
        } else {
          nameEl.textContent = filename;
          contentEl.textContent = data.content;
        }
      })
      .catch(err => {
        nameEl.textContent = filename + ' (failed)';
        contentEl.textContent = String(err);
      });
  };

  // Wire up file items with data attributes
  function initFileItems() {
    document.querySelectorAll('.file-item').forEach(el => {
      const name = el.querySelector('.file-name')?.textContent?.trim();
      if (name) {
        el.dataset.filename = name;
        el.onclick = () => window.loadFile(name);
      }
    });
  }

  // -----------------------------------------------------------------------
  // File restore
  // -----------------------------------------------------------------------
  function initRestore() {
    const btn = document.getElementById('restore-btn');
    if (!btn) return;

    btn.addEventListener('click', async () => {
      if (!confirm('Restore all files to their original state? This will undo any changes you made.')) {
        return;
      }
      btn.disabled = true;
      btn.textContent = '⏳ Restoring…';

      try {
        const resp = await fetch(`/api/challenge/${encodeURIComponent(CHALLENGE_ID)}/restore`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        const data = await resp.json();

        if (data.success) {
          // Refresh file list in explorer
          refreshFileList(data.files);
          showToast('✅ Files restored to original state!', 'success');

          // If in terminal tab, print a message
          if (term) {
            term.write(`\r\n${ANSI.GREEN}[Files have been restored to original state]${ANSI.RESET}\r\n`);
          }
        } else {
          showToast('Failed to restore files', 'error');
        }
      } catch (err) {
        showToast('Restore failed: ' + err.message, 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = '🔄 Restore Files';
      }
    });
  }

  function refreshFileList(files) {
    const list = document.getElementById('file-list');
    if (!list) return;
    list.innerHTML = '';
    files.forEach(f => {
      const btn = document.createElement('button');
      btn.className = 'file-item';
      btn.dataset.filename = f;
      btn.innerHTML = `<span class="file-icon">${f.includes('/') ? '📁' : '📄'}</span><span class="file-name">${f}</span>`;
      btn.onclick = () => window.loadFile(f);
      list.appendChild(btn);
    });
  }

  // -----------------------------------------------------------------------
  // Init
  // -----------------------------------------------------------------------
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof CHALLENGE_ID !== 'undefined') {
      initTerminal();
      initFileItems();
      initRestore();
    }
  });
})();
