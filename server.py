from flask import Flask, request, jsonify, send_from_directory
import json, os, time, datetime

# Универсальный путь: папка, где лежит server.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=BASE_DIR)
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
MESSAGES_FILE = os.path.join(BASE_DIR, 'messages.json')
CHATS_FILE = os.path.join(BASE_DIR, 'chats.json')

def load_json(path, default):
    if not os.path.exists(path): return default
    try:
        with open(path, 'r', encoding='utf-8') as f: return json.load(f)
    except: return default

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    users = load_json(USERS_FILE, {})
    if email in users:
        return jsonify({'ok': False, 'error': 'Такой email уже зарегистрирован'}), 400
    user_id = 'U' + str(int(time.time() * 1000))[-8:]
    users[email] = {
        'id': user_id, 'name': name, 'email': email,
        'passwordHash': pwd_hash, 'deviceId': device_id,
        'createdAt': datetime.datetime.utcnow().isoformat()
    }
    save_json(USERS_FILE, users)
    return jsonify({'ok': True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    pwd_hash = data.get('passwordHash', '')
    device_id = data.get('deviceId', '').strip()
    if not email or not pwd_hash or not device_id:
        return jsonify({'ok': False, 'error': 'Введите email и пароль'}), 400
    users = load_json(USERS_FILE, {})
    user = users.get(email)
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
    users = load_json(USERS_FILE, {})
    result = []
    for email, u in users.items():
        if u.get('id') == my_id: continue
        result.append({'id': u['id'], 'name': u['name']})
    return jsonify({'ok': True, 'users': result})

@app.route('/api/chats', methods=['GET'])
def get_chats():
    my_id = request.args.get('myId', '').strip()
    chats = load_json(CHATS_FILE, [])
    my_chats = [c for c in chats if my_id in c.get('members', [])]
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
    chats = load_json(CHATS_FILE, [])
    chat_id = 'C' + str(int(time.time() * 1000))[-8:]
    chats.append({
        'id': chat_id,
        'name': name,
        'type': chat_type,
        'creatorId': creator_id,
        'creatorName': creator_name,
        'members': [creator_id],
        'createdAt': datetime.datetime.utcnow().isoformat()
    })
    save_json(CHATS_FILE, chats)
    return jsonify({'ok': True, 'chatId': chat_id})

@app.route('/api/chats/<chat_id>/join', methods=['POST'])
def join_chat(chat_id):
    data = request.get_json()
    user_id = data.get('userId', '').strip()
    if not user_id:
        return jsonify({'ok': False, 'error': 'Не авторизован'}), 400
    chats = load_json(CHATS_FILE, [])
    for c in chats:
        if c['id'] == chat_id:
            if user_id not in c.get('members', []):
                c.setdefault('members', []).append(user_id)
                save_json(CHATS_FILE, chats)
            return jsonify({'ok': True})
    return jsonify({'ok': False, 'error': 'Чат не найден'}), 404

@app.route('/api/chats/available', methods=['GET'])
def available_chats():
    my_id = request.args.get('myId', '').strip()
    chats = load_json(CHATS_FILE, [])
    result = []
    for c in chats:
        if my_id not in c.get('members', []):
            result.append({
                'id': c['id'],
                'name': c['name'],
                'type': c.get('type', 'group'),
                'membersCount': len(c.get('members', []))
            })
    return jsonify({'ok': True, 'chats': result})

@app.route('/api/messages', methods=['GET'])
def get_messages():
    chat_id = request.args.get('chatId', '').strip()
    if not chat_id:
        return jsonify({'ok': True, 'messages': []})
    messages = load_json(MESSAGES_FILE, [])
    filtered = [m for m in messages if m.get('chatId') == chat_id]
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
    chats = load_json(CHATS_FILE, [])
    chat = next((c for c in chats if c['id'] == chat_id), None)
    if not chat:
        return jsonify({'ok': False, 'error': 'Чат не найден'}), 404
    if from_id not in chat.get('members', []):
        return jsonify({'ok': False, 'error': 'Вы не участник'}), 403
    if chat.get('type') == 'channel' and chat.get('creatorId') != from_id:
        return jsonify({'ok': False, 'error': 'В канале пишет только владелец'}), 403
    messages = load_json(MESSAGES_FILE, [])
    messages.append({
        'id': str(int(time.time() * 1000)),
        'chatId': chat_id,
        'from': from_id, 'fromName': from_name,
        'text': text,
        'time': datetime.datetime.utcnow().isoformat()
    })
    if len(messages) > 1000: messages = messages[-1000:]
    save_json(MESSAGES_FILE, messages)
    return jsonify({'ok': True})

@app.route('/api/reset-device', methods=['POST'])
def reset_device():
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    pwd_hash = data.get('passwordHash', '')
    new_device_id = data.get('newDeviceId', '').strip()
    if not email or not pwd_hash or not new_device_id:
        return jsonify({'ok': False, 'error': 'Некорректные данные'}), 400
    users = load_json(USERS_FILE, {})
    user = users.get(email)
    if not user or user.get('passwordHash') != pwd_hash:
        return jsonify({'ok': False, 'error': 'Неверный email или пароль'}), 401
    user['deviceId'] = new_device_id
    save_json(USERS_FILE, users)
    return jsonify({'ok': True, 'message': 'Привязка сброшена.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)
