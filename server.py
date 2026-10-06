from flask import Flask, request, jsonify, send_from_directory
import json, os, time, datetime
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

GIST_ID = "99aa3e189f2778cf1e8c6a1802bc737e"
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')

app = Flask(__name__, static_folder=BASE_DIR)

def load_db():
    try:
        req = urllib.request.Request(
            f"https://api.github.com/gists/{GIST_ID}",
            headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            content = data['files']['db.json']['content']
            db = json.loads(content) if content.strip() else {}
            db.setdefault("users", {})
            db.setdefault("chats", [])
            db.setdefault("messages", [])
            db.setdefault("dms", [])
            return db
    except Exception as e:
        print(f"Ошибка чтения Gist: {e}")
        return {"users": {}, "chats": [], "messages": [], "dms": []}

def save_db(db):
    try:
        body = json.dumps({"files": {"db.json": {"content": json.dumps(db, ensure_ascii=False)}}}).encode('utf-8')
        req = urllib.request.Request(
            f"https://api.github.com/gists/{GIST_ID}",
            data=body,
            headers={"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json", "Content-Type": "application/json"},
            method='PATCH'
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Ошибка записи Gist: {e}")
        return False

@app.route('/')
def root():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def static_file(filename):
    return send_from_directory(BASE_DIR, filename)
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    name = data.get('name', '').strip()
    pwd_hash = data.get('passwordHash', '')
    device_id = data.get('deviceId', '').strip()
    if not email or not name or not pwd_hash or not device_id:
        return jsonify({'ok': False, 'error': 'Заполните все поля'}), 400
    db = load_db()
    users = db['users']
    if email in users:
        return jsonify({'ok': False, 'error': 'Такой email уже зарегистрирован'}), 400
    user_id = 'U' + str(int(time.time() * 1000))[-8:]
    users[email] = {
        'id': user_id, 'name': name, 'email': email,
        'passwordHash': pwd_hash, 'deviceId': device_id,
        'createdAt': datetime.datetime.utcnow().isoformat()
    }
    if not save_db(db):
        return jsonify({'ok': False, 'error': 'Ошибка сохранения'}), 500
    return jsonify({'ok': True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    pwd_hash = data.get('passwordHash', '')
    device_id = data.get('deviceId', '').strip()
    if not email or not pwd_hash or not device_id:
        return jsonify({'ok': False, 'error': 'Введите email и пароль'}), 400
    db = load_db()
    user = db['users'].get(email)
    if not user or user.get('passwordHash') != pwd_hash:
        return jsonify({'ok': False, 'error': 'Неверный email или пароль'}), 401
    saved_device = user.get('deviceId', '')
    if saved_device and saved_device != device_id:
        return jsonify({'ok': False, 'error': 'Аккаунт привязан к другому устройству.'}), 403
    return jsonify({'ok': True, 'user': {
        'id': user['id'], 'name': user['name'],
        'email': user['email'], 'createdAt': user['createdAt']
    }})

@app.route('/api/users', methods=['GET'])
def get_users():
    my_id = request.args.get('myId', '').strip()
    db = load_db()
    result = []
    for email, u in db['users'].items():
        if u.get('id') == my_id: continue
        result.append({'id': u['id'], 'name': u['name']})
    return jsonify({'ok': True, 'users': result})

@app.route('/api/chats', methods=['GET'])
def get_chats():
    my_id = request.args.get('myId', '').strip()
    db = load_db()
    my_chats = [c for c in db['chats'] if my_id in c.get('members', [])]
    return jsonify({'ok': True, 'chats': my_chats})

@app.route('/api/chats', methods=['POST'])
def create_chat():
    data = request.get_json()
    creator_id = data.get('creatorId', '').strip()
    creator_name = data.get('creatorName', '').strip()
    name = data.get('name', '').strip()
    chat_type = data.get('type', 'group').strip()
    if not creator_id or not creator_name or not name:
        return jsonify({'ok': False, 'error': 'Заполните название'}), 400
    if len(name) > 60:
        return jsonify({'ok': False, 'error': 'Слишком длинное название'}), 400
    if chat_type not in ('group', 'channel'):
        chat_type = 'group'
    db = load_db()
    chat_id = 'C' + str(int(time.time() * 1000))[-8:]
    db['chats'].append({
        'id': chat_id, 'name': name, 'type': chat_type,
        'creatorId': creator_id, 'creatorName': creator_name,
        'members': [creator_id],
        'createdAt': datetime.datetime.utcnow().isoformat()
    })
    if not save_db(db):
        return jsonify({'ok': False, 'error': 'Ошибка сохранения'}), 500
    return jsonify({'ok': True, 'chatId': chat_id})

@app.route('/api/chats/<chat_id>/join', methods=['POST'])
def join_chat(chat_id):
    data = request.get_json()
    user_id = data.get('userId', '').strip()
    if not user_id:
        return jsonify({'ok': False, 'error': 'Не авторизован'}), 400
    db = load_db()
    for c in db['chats']:
        if c['id'] == chat_id:
            if user_id not in c.get('members', []):
                c.setdefault('members', []).append(user_id)
                save_db(db)
            return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Чат не найден'}), 404

@app.route('/api/chats/available', methods=['GET'])
def available_chats():
    my_id = request.args.get('myId', '').strip()
    db = load_db()
    result = []
    for c in db['chats']:
        if my_id not in c.get('members', []):
            result.append({'id': c['id'], 'name': c['name'], 'type': c.get('type', 'group'), 'membersCount': len(c.get('members', []))})
    return jsonify({'ok': True, 'chats': result})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    chat_id = request.args.get('chatId', '').strip()
    if not chat_id:
        return jsonify({'ok': True, 'messages': []})
    db = load_db()
    filtered = [m for m in db['messages'] if m.get('chatId') == chat_id]
    return jsonify({'ok': True, 'messages': filtered[-100:]})

@app.route('/api/messages', methods=['POST'])
def send_message():
    data = request.get_json()
    from_id = data.get('fromId', '').strip()
    from_name = data.get('fromName', '').strip()
    chat_id = data.get('chatId', '').strip()
    text = data.get('text', '').strip()
    if not from_id or not from_name or not chat_id or not text:
        return jsonify({'ok': False, 'error': 'Пустое сообщение'}), 400
    if len(text) > 1000:
        return jsonify({'ok': False, 'error': 'Сообщение слишком длинное'}), 400
    db = load_db()
    chat = next((c for c in db['chats'] if c['id'] == chat_id), None)
    if not chat:
        return jsonify({'ok': False, 'error': 'Чат не найден'}), 404
    if from_id not in chat.get('members', []):
        return jsonify({'ok': False, 'error': 'Вы не участник'}), 403
    if chat.get('type') == 'channel' and chat.get('creatorId') != from_id:
        return jsonify({'ok': False, 'error': 'В канале пишет только владелец'}), 403
    db['messages'].append({
        'id': str(int(time.time() * 1000)), 'chatId': chat_id,
        'from': from_id, 'fromName': from_name,
        'text': text, 'time': datetime.datetime.utcnow().isoformat()
    })
    if len(db['messages']) > 1000: db['messages'] = db['messages'][-1000:]
    if not save_db(db):
        return jsonify({'ok': False, 'error': 'Ошибка сохранения'}), 500
    return jsonify({'ok': True})
@app.route('/api/dm/start', methods=['POST'])
def dm_start():
    data = request.get_json()
    my_id = data.get('myId', '').strip()
    peer_id = data.get('peerId', '').strip()
    if not my_id or not peer_id or my_id == peer_id:
        return jsonify({'ok': False, 'error': 'Некорректные данные'}), 400
    db = load_db()
    for dm in db['dms']:
        if set(dm.get('members', [])) == {my_id, peer_id}:
            return jsonify({'ok': True, 'dmId': dm['id'], 'exists': True})
    dm_id = 'D' + str(int(time.time() * 1000))[-8:]
    db['dms'].append({
        'id': dm_id,
        'members': [my_id, peer_id],
        'createdAt': datetime.datetime.utcnow().isoformat()
    })
    if not save_db(db):
        return jsonify({'ok': False, 'error': 'Ошибка сохранения'}), 500
    return jsonify({'ok': True, 'dmId': dm_id, 'exists': False})

@app.route('/api/dm/list', methods=['GET'])
def dm_list():
    my_id = request.args.get('myId', '').strip()
    db = load_db()
    result = []
    for dm in db['dms']:
        if my_id not in dm.get('members', []): continue
        peer_id = next((m for m in dm['members'] if m != my_id), None)
        if not peer_id: continue
        peer_name = '?'
        for email, u in db['users'].items():
            if u.get('id') == peer_id:
                peer_name = u.get('name', '?')
                break
        last_msg = None
        for m in db['messages']:
            if m.get('dmId') == dm['id']:
                last_msg = m
        result.append({
            'id': dm['id'], 'peerId': peer_id, 'peerName': peer_name,
            'lastMessage': last_msg.get('text', '') if last_msg else '',
            'lastTime': last_msg.get('time', '') if last_msg else ''
        })
    return jsonify({'ok': True, 'dms': result})

@app.route('/api/dm/messages', methods=['GET'])
def dm_messages():
    dm_id = request.args.get('dmId', '').strip()
    if not dm_id:
        return jsonify({'ok': True, 'messages': []})
    db = load_db()
    filtered = [m for m in db['messages'] if m.get('dmId') == dm_id]
    return jsonify({'ok': True, 'messages': filtered[-100:]})

@app.route('/api/dm/send', methods=['POST'])
def dm_send():
    data = request.get_json()
    from_id = data.get('fromId', '').strip()
    from_name = data.get('fromName', '').strip()
    dm_id = data.get('dmId', '').strip()
    text = data.get('text', '').strip()
    if not from_id or not from_name or not dm_id or not text:
        return jsonify({'ok': False, 'error': 'Пустое сообщение'}), 400
    if len(text) > 1000:
        return jsonify({'ok': False, 'error': 'Слишком длинное'}), 400
    db = load_db()
    dm = next((d for d in db['dms'] if d['id'] == dm_id), None)
    if not dm:
        return jsonify({'ok': False, 'error': 'Диалог не найден'}), 404
    if from_id not in dm.get('members', []):
        return jsonify({'ok': False, 'error': 'Вы не участник'}), 403
    db['messages'].append({
        'id': str(int(time.time() * 1000)),
        'dmId': dm_id,
        'from': from_id, 'fromName': from_name,
        'text': text, 'time': datetime.datetime.utcnow().isoformat()
    })
    if len(db['messages']) > 1000: db['messages'] = db['messages'][-1000:]
    if not save_db(db):
        return jsonify({'ok': False, 'error': 'Ошибка сохранения'}), 500
    return jsonify({'ok': True})

@app.route('/api/reset-device', methods=['POST'])
def reset_device():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    pwd_hash = data.get('passwordHash', '')
    new_device_id = data.get('newDeviceId', '').strip()
    if not email or not pwd_hash or not new_device_id:
        return jsonify({'ok': False, 'error': 'Некорректные данные'}), 400
    db = load_db()
    user = db['users'].get(email)
    if not user or user.get('passwordHash') != pwd_hash:
        return jsonify({'ok': False, 'error': 'Неверный email или пароль'}), 401
    user['deviceId'] = new_device_id
    save_db(db)
    return jsonify({'ok': True, 'message': 'Привязка сброшена.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
