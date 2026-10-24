#!/usr/bin/env python3
"""Share a folder on your local network. Python standard library only.
Usage: python fileshare.py [port] [folder] [--no-browser]
"""
import argparse
import hmac
import html
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import tempfile
import threading
import urllib.parse as url
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ADMIN_PASSWORD = os.environ.get('FILESHARE_ADMIN_PASSWORD', '132')
ROOT = Path(__file__).resolve().parent / 'Shared Files'
SESSION_TOKEN = secrets.token_urlsafe(32)
FORM_TOKEN = secrets.token_urlsafe(32)

PAGE = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>File Share</title>
<style>
*{box-sizing:border-box}body{font:16px system-ui,sans-serif;background:#f3f6fb;color:#17243b;margin:0}main{max-width:960px;margin:40px auto;padding:0 20px}header,.bar{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}h1{margin:0}p{color:#58677d}button,.button{border:0;border-radius:9px;background:#265ed7;color:white;padding:11px 16px;cursor:pointer;font:inherit;text-decoration:none;display:inline-block}button.secondary{background:#e6ecf7;color:#234477}input{font:inherit;padding:11px;border:1px solid #cbd5e5;border-radius:8px;max-width:100%}.card{background:white;border:1px solid #dde4ef;border-radius:16px;padding:22px;margin-top:20px}#drop{border:2px dashed #b8c9e5;text-align:center;padding:30px;cursor:pointer}#drop.over{background:#e8f0ff;border-color:#265ed7}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:15px 8px;border-bottom:1px solid #edf0f5}td:first-child{overflow-wrap:anywhere}a{color:#265ed7;text-decoration:none}.actions{display:flex;gap:8px;flex-wrap:wrap}.actions button,.actions a{font-size:14px;padding:7px 10px}#status{white-space:pre-wrap;overflow-wrap:anywhere}progress{width:100%;margin-top:14px}small{color:#64748b}#link{flex:1;min-width:180px}dialog{border:0;border-radius:14px;padding:25px;max-width:90vw}dialog::backdrop{background:#17243b77}@media(max-width:600px){main{margin:20px auto;padding:0 12px}.card{padding:14px}td,th{padding:12px 4px}.size{display:none}h1{font-size:26px}}
</style><main><header><div><h1>File Share</h1><p>Send files between devices on the same Wi-Fi or network.</p></div>__ADMIN__</header>
<div class="card bar"><input id="link" readonly aria-label="Share link"><small>Select the link and copy it manually.</small></div>
<div class="card"><div class="bar"><strong>__PATH__</strong><a href="/">Home</a></div><p>__UP__</p>
<div id="drop" tabindex="0" role="button" aria-label="Choose files to upload"><strong>Drop files here or choose files</strong><p>Multiple files welcome. Existing files are kept.</p><input id="files" type="file" multiple hidden><button id="choose" type="button">Choose files</button></div><progress id="progress" value="0" max="100" hidden></progress><p id="status" role="status" aria-live="polite"></p>
__MKDIR__<div class="bar"><h2>Files <small>(__COUNT__)</small></h2><input id="search" placeholder="Search this folder" aria-label="Search this folder"></div><table><thead><tr><th>Name</th><th class="size">Size</th><th>Actions</th></tr></thead><tbody>__ROWS__</tbody></table><p id="empty" hidden>No matching files.</p></div><p><small>Keep this window's launcher running while sharing. Stop it with Ctrl+C.</small></p>
<dialog id="login"><form method="post" action="/login?path=__QPATH__"><input type="hidden" name="token" value="__TOKEN__"><h2>Admin unlock</h2><p>Create folders and delete files.</p><input type="password" name="password" placeholder="Admin password" required autocomplete="current-password"><p><button>Unlock</button> <button type="button" class="secondary" onclick="document.querySelector('dialog').close()">Cancel</button></p></form></dialog>
<script>
const current=__REL__, token=__JTOKEN__, picker=document.querySelector('#files'), drop=document.querySelector('#drop'), statusEl=document.querySelector('#status'), progress=document.querySelector('#progress');
document.querySelector('#link').value=location.href;
drop.onclick=()=>picker.click();drop.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();picker.click()}};
for(const type of ['dragover','dragleave','drop'])drop.addEventListener(type,e=>{e.preventDefault();drop.classList.toggle('over',type==='dragover')});
drop.addEventListener('drop',e=>upload(e.dataTransfer.files));picker.onchange=()=>upload(picker.files);
let busy=false;
async function upload(files){if(busy||!files.length)return;busy=true;progress.hidden=false;const results=[];let failed=false;try{for(let i=0;i<files.length;i++){const f=files[i];statusEl.textContent=`Uploading ${i+1}/${files.length}: ${f.name}`;await new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('POST','/upload?path='+encodeURIComponent(current)+'&name='+encodeURIComponent(f.name));x.setRequestHeader('X-Share-Token',token);x.upload.onprogress=e=>{if(e.lengthComputable)progress.value=e.loaded/e.total*100};x.onload=()=>{if(x.status===201){results.push(JSON.parse(x.responseText).name);resolve()}else reject(new Error(x.responseText||'Upload failed'))};x.onerror=()=>reject(new Error('Connection lost. Check the server and try again.'));x.send(f)})}sessionStorage.setItem('uploaded',results.length+' file(s) uploaded.');location.reload()}catch(e){failed=true;statusEl.textContent=results.length+' uploaded. '+e.message}finally{busy=false;picker.value='';if(failed)progress.hidden=true}}
const message=sessionStorage.getItem('uploaded');if(message){statusEl.textContent=message;sessionStorage.removeItem('uploaded')}
document.querySelector('#search').oninput=e=>{let visible=0;document.querySelectorAll('tr[data-name]').forEach(r=>{r.hidden=!r.dataset.name.includes(e.target.value.toLowerCase());if(!r.hidden)visible++});document.querySelector('#empty').hidden=visible>0};
document.querySelectorAll('.delete').forEach(f=>f.onsubmit=()=>confirm('Delete this item and its contents? This cannot be undone.'));
</script></main></html>'''


def safe_join(rel):
    path = (ROOT / rel).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise ValueError('This path is outside the shared folder.')
    return path


def valid_name(name):
    if not name or name in ('.', '..') or any(c in name for c in '/\\\x00<>:"|?*') or any(ord(c) < 32 for c in name) or name.endswith((' ', '.')):
        raise ValueError('Choose a valid file or folder name without path separators.')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('This name is reserved by Windows.')
    return name


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
        n /= 1024


class Handler(BaseHTTPRequestHandler):
    def send(self, code, body, content_type='text/plain; charset=utf-8', headers=()):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Cache-Control', 'no-store')
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def redirect(self, rel='', headers=()):
        self.send(303, '', headers=[('Location', '/?path=' + url.quote(rel, safe='')), *headers])

    def admin(self):
        try:
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            return 'fs_admin' in cookie and hmac.compare_digest(cookie['fs_admin'].value, SESSION_TOKEN)
        except Exception:
            return False

    def route(self):
        parsed = url.urlsplit(self.path)
        query = url.parse_qs(parsed.query)
        return parsed.path, query.get('path', [''])[0], query

    def do_GET(self):
        try:
            route, rel, _ = self.route()
            target = safe_join(rel)
            if route == '/download':
                if not target.is_file():
                    return self.send(404, 'File not found.')
                with target.open('rb') as source:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(os.fstat(source.fileno()).st_size))
                    self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + url.quote(target.name, safe=''))
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.end_headers()
                    shutil.copyfileobj(source, self.wfile, 1024 * 1024)
                return
            if route != '/':
                return self.send(404, 'Not found.')
            if not target.is_dir():
                return self.send(404, 'Folder not found.')
            admin = self.admin()
            esc = html.escape
            qrel = url.quote(rel, safe='')
            rows = []
            for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if entry.is_symlink() or entry.name.startswith('.fileshare-upload-'):
                    continue
                child = entry.relative_to(ROOT).as_posix()
                query = url.quote(child, safe='')
                folder = entry.is_dir()
                action = f'<a class="button" href="/download?path={query}">Download</a>' if not folder else ''
                if admin:
                    action += f'<form class="delete" method="post" action="/delete?path={query}"><input type="hidden" name="token" value="{FORM_TOKEN}"><button class="secondary">Delete</button></form>'
                href = '/?path=' if folder else '/download?path='
                rows.append(f'<tr data-name="{esc(entry.name.lower(), quote=True)}"><td><a href="{href}{query}">{"📁" if folder else "📄"} {esc(entry.name)}</a></td><td class="size">{"—" if folder else human_size(entry.stat().st_size)}</td><td><div class="actions">{action}</div></td></tr>')
            admin_ui = f'<form method="post" action="/logout?path={qrel}"><input type="hidden" name="token" value="{FORM_TOKEN}"><button class="secondary">Lock admin</button></form>' if admin else '<button class="secondary" onclick="document.querySelector(\'dialog\').showModal()">Admin unlock</button>'
            mkdir = f'<form method="post" action="/mkdir?path={qrel}"><input type="hidden" name="token" value="{FORM_TOKEN}"><p class="bar"><input name="foldername" placeholder="New folder name" required><button>Create folder</button></p></form>' if admin else ''
            values = {'ADMIN': admin_ui, 'PATH': esc('/' + rel), 'UP': f'<a href="/?path={url.quote(str(Path(rel).parent).replace(chr(92), "/"), safe="")}">↑ Parent folder</a>' if rel else 'Ready to share', 'MKDIR': mkdir, 'COUNT': str(len(rows)), 'ROWS': ''.join(rows) or '<tr><td colspan="3">No files yet. Upload your first file above.</td></tr>', 'QPATH': qrel, 'TOKEN': FORM_TOKEN, 'REL': json.dumps(rel).replace('<', '\\u003c'), 'JTOKEN': json.dumps(FORM_TOKEN)}
            import re
            page = re.sub(r'__([A-Z]+)__', lambda m: values[m[1]], PAGE)
            self.send(200, page, 'text/html; charset=utf-8')
        except (ValueError, OSError) as e:
            self.send(400, str(e))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def do_POST(self):
        try:
            route, rel, query = self.route()
            target = safe_join(rel)
            length = int(self.headers.get('Content-Length', '-1'))
            if length < 0:
                return self.send(411, 'Content-Length required.')
            if route == '/upload':
                if not hmac.compare_digest(self.headers.get('X-Share-Token', ''), FORM_TOKEN):
                    return self.send(403, 'Reload the page and try again.')
                if not target.is_dir():
                    return self.send(404, 'Folder not found.')
                name = valid_name(query.get('name', [''])[0])
                temp = None
                try:
                    with tempfile.NamedTemporaryFile(prefix='.fileshare-upload-', dir=target, delete=False) as out:
                        temp = Path(out.name)
                        remaining = length
                        while remaining:
                            chunk = self.rfile.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise ValueError('Upload interrupted. Please retry.')
                            out.write(chunk)
                            remaining -= len(chunk)
                    # Reserve the destination exclusively, preserving files with duplicate names.
                    counter = 0
                    while True:
                        candidate = name if counter == 0 else f'{Path(name).stem} ({counter}){Path(name).suffix}'
                        dest = target / candidate
                        try:
                            with dest.open('xb') as out, temp.open('rb') as source:
                                try:
                                    shutil.copyfileobj(source, out, 1024 * 1024)
                                except BaseException:
                                    dest.unlink(missing_ok=True)
                                    raise
                            break
                        except FileExistsError:
                            counter += 1
                    self.send(201, json.dumps({'name': candidate}), 'application/json')
                finally:
                    if temp:
                        temp.unlink(missing_ok=True)
                return
            if length > 16384:
                return self.send(413, 'Form is too large.')
            data = url.parse_qs(self.rfile.read(length).decode())
            if not hmac.compare_digest(data.get('token', [''])[0], FORM_TOKEN):
                return self.send(403, 'Reload the page and try again.')
            if route == '/login':
                if not hmac.compare_digest(data.get('password', [''])[0].encode(), ADMIN_PASSWORD.encode()):
                    return self.send(403, 'Incorrect admin password. Go back and try again.')
                return self.redirect(rel, [('Set-Cookie', f'fs_admin={SESSION_TOKEN}; HttpOnly; SameSite=Strict; Path=/')])
            if route == '/logout':
                return self.redirect(rel, [('Set-Cookie', 'fs_admin=; Max-Age=0; HttpOnly; SameSite=Strict; Path=/')])
            if not self.admin():
                return self.send(403, 'Unlock admin first.')
            if route == '/mkdir':
                (target / valid_name(data.get('foldername', [''])[0].strip())).mkdir()
                return self.redirect(rel)
            if route == '/delete':
                if target == ROOT:
                    return self.send(403, 'The shared root cannot be deleted.')
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                return self.redirect(target.parent.relative_to(ROOT).as_posix())
            self.send(404, 'Not found.')
        except (ValueError, OSError) as e:
            self.send(400, str(e))



class ShareServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can allow a second listener on an occupied port.
    # Require exclusive ownership so binding fails and triggers fallback.
    allow_reuse_address = False
    allow_reuse_port = False
    daemon_threads = True

    def server_bind(self):
        if os.name == 'nt' and hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def start_server(preferred_port):
    candidates = list(dict.fromkeys([preferred_port, 8000, 0]))
    last_error = None
    for port in candidates:
        try:
            return ShareServer(('0.0.0.0', port), Handler)
        except OSError as error:
            last_error = error
            print(f'Port {port} unavailable: {error}', flush=True)
            print('Trying another port...', flush=True)
    raise last_error


def main():
    global ROOT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port', type=int, nargs='?', default=80)
    parser.add_argument('folder', nargs='?', default=str(ROOT))
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    ROOT = Path(args.folder).expanduser().resolve()
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        server = start_server(args.port)
    except OSError as error:
        parser.exit(1, f'Cannot start file sharing: {error}\n')
    ip = '127.0.0.1'
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
    except OSError:
        pass
    port = server.server_port
    link = f'http://{ip}' + (f':{port}' if port != 80 else '')
    if port != args.port:
        print(f'PORT CHANGED: {args.port} -> {port}', flush=True)
    if os.name == 'nt':
        import ctypes
        ctypes.windll.kernel32.SetConsoleTitleW(f'File Share - PORT {port} - {link}')
    print(f'\nFILE SHARE - RUNNING ON PORT {port}\nShared folder: {ROOT}\n\nOpen on your other device: {link}\n\nAnyone on this network can upload and download.\nAdmin password: configured in ADMIN_PASSWORD or FILESHARE_ADMIN_PASSWORD.\nIf Windows asks, allow access on your private network.\nPress Ctrl+C to stop.\n', flush=True)
    if not args.no_browser:
        threading.Timer(0.7, lambda: webbrowser.open(link)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nSharing stopped.')
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
