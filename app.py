"""
GitHub Copilot CLI Learning Website
Flask backend with WebSocket terminal support
"""

import os
import pty
import select
import subprocess
import shutil
import threading
import json
import uuid
import signal
from pathlib import Path

import requests
import markdown
from flask import (
    Flask, session, redirect, url_for,
    render_template, request, jsonify, abort
)
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24).hex())

socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode='threading',
    logger=False,
    engineio_logger=False
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
GITHUB_CLIENT_ID = os.environ.get('GITHUB_CLIENT_ID', '')
GITHUB_CLIENT_SECRET = os.environ.get('GITHUB_CLIENT_SECRET', '')
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

CHALLENGES_DIR = Path(__file__).parent / 'challenges'
SANDBOXES_DIR = Path(__file__).parent / 'sandboxes'
SANDBOXES_DIR.mkdir(exist_ok=True)

# Active PTY terminal sessions: sid -> {fd, process, sandbox_path}
terminals: dict = {}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_challenges():
    """Load all challenge metadata from challenges directory."""
    challenges = []
    for challenge_dir in sorted(CHALLENGES_DIR.iterdir()):
        info_file = challenge_dir / 'info.json'
        if challenge_dir.is_dir() and info_file.exists():
            with open(info_file) as f:
                data = json.load(f)
            data['id'] = challenge_dir.name
            data['files'] = list_challenge_files(challenge_dir / 'files')
            challenges.append(data)
    return challenges


def list_challenge_files(files_dir: Path):
    """Return a list of relative file paths in a challenge's files directory."""
    if not files_dir.exists():
        return []
    result = []
    for p in sorted(files_dir.rglob('*')):
        if p.is_file():
            result.append(str(p.relative_to(files_dir)))
    return result


def get_sandbox_path(session_id: str, challenge_id: str) -> Path:
    return SANDBOXES_DIR / session_id / challenge_id


def create_sandbox(session_id: str, challenge_id: str) -> Path:
    """Copy challenge files into an isolated sandbox directory."""
    sandbox = get_sandbox_path(session_id, challenge_id)
    if sandbox.exists():
        shutil.rmtree(sandbox)
    src = CHALLENGES_DIR / challenge_id / 'files'
    if src.exists():
        shutil.copytree(src, sandbox)
    else:
        sandbox.mkdir(parents=True, exist_ok=True)
    return sandbox


def restore_sandbox(session_id: str, challenge_id: str) -> Path:
    """Restore sandbox files to original challenge state."""
    return create_sandbox(session_id, challenge_id)


def get_file_content(sandbox_path: Path, filename: str) -> str:
    """Safely read a file from the sandbox, preventing path traversal."""
    target = (sandbox_path / filename).resolve()
    if not str(target).startswith(str(sandbox_path.resolve())):
        raise PermissionError("Path traversal detected")
    if not target.is_file():
        raise FileNotFoundError(f"{filename} not found")
    return target.read_text(errors='replace')


def require_login(f):
    """Decorator that redirects to login if user is not authenticated."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    challenges = load_challenges()
    return render_template('index.html', user=session['user'], challenges=challenges)


@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('index'))
    return render_template('login.html',
                           github_client_id=GITHUB_CLIENT_ID,
                           demo_mode=not GITHUB_CLIENT_ID)


@app.route('/login/github')
def github_login():
    if not GITHUB_CLIENT_ID:
        # Demo mode: create a fake user
        session['user'] = {
            'login': 'demo-user',
            'name': 'Demo User',
            'avatar_url': 'https://github.com/identicons/demo',
        }
        session['session_id'] = str(uuid.uuid4())
        return redirect(url_for('index'))

    callback_url = f"{BASE_URL}/auth/callback"
    auth_url = (
        f"https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={callback_url}"
        f"&scope=read:user"
    )
    return redirect(auth_url)


@app.route('/auth/callback')
def auth_callback():
    code = request.args.get('code')
    if not code:
        return redirect(url_for('login'))

    # Exchange code for token
    resp = requests.post(
        'https://github.com/login/oauth/access_token',
        data={
            'client_id': GITHUB_CLIENT_ID,
            'client_secret': GITHUB_CLIENT_SECRET,
            'code': code,
        },
        headers={'Accept': 'application/json'},
        timeout=10,
    )
    token_data = resp.json()
    access_token = token_data.get('access_token')
    if not access_token:
        return redirect(url_for('login'))

    # Get user profile
    user_resp = requests.get(
        'https://api.github.com/user',
        headers={
            'Authorization': f'token {access_token}',
            'Accept': 'application/json',
        },
        timeout=10,
    )
    user = user_resp.json()
    session['user'] = {
        'login': user.get('login'),
        'name': user.get('name') or user.get('login'),
        'avatar_url': user.get('avatar_url'),
        'access_token': access_token,
    }
    session['session_id'] = str(uuid.uuid4())
    return redirect(url_for('index'))


@app.route('/logout')
def logout():
    # Clean up any sandboxes for this session
    sid = session.get('session_id')
    if sid:
        session_sandbox = SANDBOXES_DIR / sid
        if session_sandbox.exists():
            shutil.rmtree(session_sandbox, ignore_errors=True)
    session.clear()
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Challenge routes
# ---------------------------------------------------------------------------

@app.route('/challenge/<challenge_id>')
@require_login
def challenge(challenge_id):
    info_file = CHALLENGES_DIR / challenge_id / 'info.json'
    if not info_file.exists():
        abort(404)
    with open(info_file) as f:
        challenge_data = json.load(f)
    challenge_data['id'] = challenge_id

    # Render instructions as HTML
    instructions_md = challenge_data.get('instructions', '')
    challenge_data['instructions_html'] = markdown.markdown(
        instructions_md,
        extensions=['fenced_code', 'codehilite', 'tables', 'nl2br']
    )

    session_id = session.get('session_id', str(uuid.uuid4()))
    session['session_id'] = session_id

    # Prepare sandbox
    sandbox = create_sandbox(session_id, challenge_id)

    # List challenge files for the file explorer
    files = list_challenge_files(sandbox)

    challenges = load_challenges()

    return render_template(
        'challenge.html',
        user=session['user'],
        challenge=challenge_data,
        challenges=challenges,
        files=files,
        session_id=session_id,
    )


@app.route('/api/challenge/<challenge_id>/files')
@require_login
def api_challenge_files(challenge_id):
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No session'}), 400

    sandbox = get_sandbox_path(session_id, challenge_id)
    if not sandbox.exists():
        sandbox = create_sandbox(session_id, challenge_id)

    files = list_challenge_files(sandbox)
    return jsonify({'files': files})


@app.route('/api/challenge/<challenge_id>/file')
@require_login
def api_get_file(challenge_id):
    filename = request.args.get('name', '')
    if not filename:
        return jsonify({'error': 'filename required'}), 400

    session_id = session.get('session_id')
    sandbox = get_sandbox_path(session_id, challenge_id)

    try:
        content = get_file_content(sandbox, filename)
        return jsonify({'content': content, 'name': filename})
    except (PermissionError, FileNotFoundError) as e:
        return jsonify({'error': str(e)}), 404


@app.route('/api/challenge/<challenge_id>/restore', methods=['POST'])
@require_login
def api_restore(challenge_id):
    session_id = session.get('session_id')
    if not session_id:
        return jsonify({'error': 'No session'}), 400

    info_file = CHALLENGES_DIR / challenge_id / 'info.json'
    if not info_file.exists():
        return jsonify({'error': 'Challenge not found'}), 404

    restore_sandbox(session_id, challenge_id)
    files = list_challenge_files(get_sandbox_path(session_id, challenge_id))
    return jsonify({'success': True, 'files': files})


# ---------------------------------------------------------------------------
# WebSocket terminal
# ---------------------------------------------------------------------------

@socketio.on('connect')
def on_connect():
    print(f'[WS] Client connected: {request.sid}')


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    print(f'[WS] Client disconnected: {sid}')
    _close_terminal(sid)


@socketio.on('start_terminal')
def on_start_terminal(data):
    sid = request.sid
    challenge_id = data.get('challenge_id', '')
    session_id = data.get('session_id', '')

    if not challenge_id or not session_id:
        emit('error', {'message': 'Missing challenge_id or session_id'})
        return

    # Close existing terminal for this socket if any
    _close_terminal(sid)

    sandbox = get_sandbox_path(session_id, challenge_id)
    if not sandbox.exists():
        sandbox = create_sandbox(session_id, challenge_id)

    _spawn_terminal(sid, sandbox)


@socketio.on('input')
def on_input(data):
    sid = request.sid
    terminal = terminals.get(sid)
    if terminal and terminal.get('fd'):
        try:
            input_data = data.get('data', '')
            os.write(terminal['fd'], input_data.encode())
        except OSError:
            _close_terminal(sid)


@socketio.on('resize')
def on_resize(data):
    sid = request.sid
    terminal = terminals.get(sid)
    if terminal and terminal.get('fd'):
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        try:
            import fcntl
            import termios
            import struct
            winsize = struct.pack('HHHH', rows, cols, 0, 0)
            fcntl.ioctl(terminal['fd'], termios.TIOCSWINSZ, winsize)
        except Exception:
            pass


def _spawn_terminal(sid: str, sandbox_path: Path):
    """Spawn a bash shell in the sandbox directory connected to a PTY."""
    master_fd, slave_fd = pty.openpty()

    env = {
        **os.environ,
        'TERM': 'xterm-256color',
        'HOME': str(sandbox_path),
        'PWD': str(sandbox_path),
        'PS1': r'\[\033[01;32m\]sandbox\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ ',
        'COLUMNS': '200',
        'LINES': '50',
    }

    process = subprocess.Popen(
        ['/bin/bash', '--norc', '--noprofile'],
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        cwd=str(sandbox_path),
        close_fds=True,
        env=env,
        preexec_fn=os.setsid,
    )
    os.close(slave_fd)

    terminals[sid] = {
        'fd': master_fd,
        'process': process,
        'sandbox_path': sandbox_path,
    }

    # Start background reader thread
    thread = threading.Thread(
        target=_read_and_forward,
        args=(sid, master_fd),
        daemon=True,
    )
    thread.start()

    # Emit a welcome banner directly to the client terminal (not via the shell)
    welcome = (
        f'\r\n\x1b[1;32m🚀 Sandbox ready!\x1b[0m  '
        f'Working directory: \x1b[33m{sandbox_path.name}\x1b[0m\r\n'
        f'\x1b[90mType commands below. Use gh copilot explain/suggest to get help.\x1b[0m\r\n\r\n'
    )
    socketio.emit('output', {'data': welcome}, room=sid)


def _read_and_forward(sid: str, fd: int):
    """Read PTY output and forward to WebSocket client."""
    max_read = 1024 * 20
    while True:
        try:
            r, _, _ = select.select([fd], [], [], 0.1)
            if fd in r:
                data = os.read(fd, max_read)
                if data:
                    socketio.emit('output', {'data': data.decode('utf-8', errors='replace')}, room=sid)
                else:
                    break
        except OSError:
            break
    # Terminal closed
    socketio.emit('terminal_closed', {}, room=sid)


def _close_terminal(sid: str):
    """Terminate the PTY process and close the file descriptor."""
    terminal = terminals.pop(sid, None)
    if not terminal:
        return
    fd = terminal.get('fd')
    process = terminal.get('process')
    if process:
        try:
            process.terminate()
            process.wait(timeout=2)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass
    if fd:
        try:
            os.close(fd)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV', 'development') == 'development'
    socketio.run(app, host='0.0.0.0', port=port, debug=debug, allow_unsafe_werkzeug=True)
