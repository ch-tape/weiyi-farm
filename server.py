import sqlite3, hashlib, time, json, os
from flask import Flask, request, jsonify, send_from_directory
from datetime import datetime

app = Flask(__name__, static_folder='.')
DB = os.path.join(os.path.dirname(__file__), 'farm.db')

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        coins INTEGER DEFAULT 100,
        created_at TEXT DEFAULT (datetime('now','localtime'))
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS plots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        plot_index INTEGER NOT NULL,
        crop_type TEXT,
        plant_time REAL,
        grow_seconds INTEGER,
        watered INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id),
        UNIQUE(user_id, plot_index)
    )''')
    conn.commit()
    conn.close()

init_db()

CROPS = {
    'wheat':  {'name':'小麦','price':5,'grow':30,'value':15,'icon':'🌾'},
    'carrot': {'name':'胡萝卜','price':10,'grow':60,'value':30,'icon':'🥕'},
    'tomato': {'name':'番茄','price':20,'grow':120,'value':55,'icon':'🍅'},
    'corn':   {'name':'玉米','price':15,'grow':90,'value':40,'icon':'🌽'},
    'melon':  {'name':'西瓜','price':50,'grow':300,'value':150,'icon':'🍉'},
    'grape':  {'name':'葡萄','price':80,'grow':480,'value':250,'icon':'🍇'},
    'sunflower':{'name':'向日葵','price':12,'grow':60,'value':35,'icon':'🌻'},
    'rose':   {'name':'玫瑰','price':30,'grow':180,'value':90,'icon':'🌹'},
    'berry':  {'name':'草莓','price':40,'grow':240,'value':120,'icon':'🍓'},
    'pepper': {'name':'辣椒','price':18,'grow':100,'value':50,'icon':'🌶️'},
    'pumpkin':{'name':'南瓜','price':60,'grow':360,'value':200,'icon':'🎃'},
    'cabbage':{'name':'白菜','price':8,'grow':45,'value':22,'icon':'🥬'},
}

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    username = data.get('username','').strip()
    password = data.get('password','')
    if not username or not password or len(username) > 20 or len(password) < 3:
        return jsonify({'ok':False,'msg':'用户名不能为空且不超过20字，密码至少3位'})
    conn = get_db()
    try:
        conn.execute('INSERT INTO users (username,password) VALUES (?,?)',
                     [username, hash_pw(password)])
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        # 初始化6块地
        for i in range(6):
            conn.execute('INSERT INTO plots (user_id,plot_index) VALUES (?,?)', [user_id, i])
        conn.commit()
        return jsonify({'ok':True,'msg':'注册成功！请登录','user_id':user_id})
    except sqlite3.IntegrityError:
        return jsonify({'ok':False,'msg':'用户名已被占用'})
    finally:
        conn.close()

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username','').strip()
    password = data.get('password','')
    conn = get_db()
    row = conn.execute('SELECT * FROM users WHERE username=? AND password=?',
                       [username, hash_pw(password)]).fetchone()
    conn.close()
    if row:
        return jsonify({'ok':True,'user':dict(row),'crops':CROPS})
    return jsonify({'ok':False,'msg':'用户名或密码错误'})

@app.route('/api/farm/<int:user_id>')
def get_farm(user_id):
    conn = get_db()
    plots = conn.execute('SELECT * FROM plots WHERE user_id=? ORDER BY plot_index', [user_id]).fetchall()
    user = conn.execute('SELECT id,username,coins FROM users WHERE id=?', [user_id]).fetchone()
    conn.close()
    now = time.time()
    result = []
    for p in plots:
        p = dict(p)
        p['state'] = 'empty'
        p['progress'] = 0
        p['can_harvest'] = False
        if p['crop_type'] and p['plant_time']:
            elapsed = now - p['plant_time']
            if elapsed >= p['grow_seconds']:
                p['state'] = 'ready'
                p['progress'] = 100
                p['can_harvest'] = True
            else:
                p['state'] = 'growing'
                p['progress'] = int(elapsed / p['grow_seconds'] * 100)
        result.append(p)
    return jsonify({'ok':True,'plots':result,'user':dict(user) if user else None})

@app.route('/api/plant', methods=['POST'])
def plant():
    data = request.json
    user_id, plot_index, crop_type = data['user_id'], data['plot_index'], data['crop_type']
    if crop_type not in CROPS:
        return jsonify({'ok':False,'msg':'无效的作物'})
    crop = CROPS[crop_type]
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE id=?', [user_id]).fetchone()
    if user['coins'] < crop['price']:
        conn.close()
        return jsonify({'ok':False,'msg':'金币不足！'})
    plot = conn.execute('SELECT * FROM plots WHERE user_id=? AND plot_index=?', [user_id, plot_index]).fetchone()
    if plot['crop_type']:
        conn.close()
        return jsonify({'ok':False,'msg':'这块地已有作物'})
    conn.execute('UPDATE users SET coins=coins-? WHERE id=?', [crop['price'], user_id])
    conn.execute('UPDATE plots SET crop_type=?,plant_time=?,grow_seconds=?,watered=0 WHERE user_id=? AND plot_index=?',
                 [crop_type, time.time(), crop['grow'], user_id, plot_index])
    conn.commit()
    coins = conn.execute('SELECT coins FROM users WHERE id=?', [user_id]).fetchone()['coins']
    conn.close()
    return jsonify({'ok':True,'msg':f'种下了{crop["name"]}！','coins':coins})

@app.route('/api/water', methods=['POST'])
def water():
    data = request.json
    user_id, plot_index = data['user_id'], data['plot_index']
    conn = get_db()
    plot = conn.execute('SELECT * FROM plots WHERE user_id=? AND plot_index=?', [user_id, plot_index]).fetchone()
    if not plot or not plot['crop_type']:
        conn.close()
        return jsonify({'ok':False,'msg':'没有作物'})
    if plot['watered']:
        conn.close()
        return jsonify({'ok':False,'msg':'已经浇过了'})
    now = time.time()
    if now - plot['plant_time'] >= plot['grow_seconds']:
        conn.close()
        return jsonify({'ok':False,'msg':'已成熟，快收吧'})
    # 浇水减少10%生长时间
    new_time = plot['plant_time'] - plot['grow_seconds'] * 0.1
    conn.execute('UPDATE plots SET plant_time=?,watered=1 WHERE user_id=? AND plot_index=?',
                 [new_time, user_id, plot_index])
    conn.commit()
    conn.close()
    return jsonify({'ok':True,'msg':'浇水成功，生长加速10%！'})

@app.route('/api/harvest', methods=['POST'])
def harvest():
    data = request.json
    user_id, plot_index = data['user_id'], data['plot_index']
    conn = get_db()
    plot = conn.execute('SELECT * FROM plots WHERE user_id=? AND plot_index=?', [user_id, plot_index]).fetchone()
    if not plot or not plot['crop_type']:
        conn.close()
        return jsonify({'ok':False,'msg':'没有作物'})
    now = time.time()
    if now - plot['plant_time'] < plot['grow_seconds']:
        conn.close()
        return jsonify({'ok':False,'msg':'还没成熟呢'})
    crop = CROPS.get(plot['crop_type'], {'value':0,'name':'未知'})
    conn.execute('UPDATE users SET coins=coins+? WHERE id=?', [crop['value'], user_id])
    conn.execute('UPDATE plots SET crop_type=NULL,plant_time=NULL,grow_seconds=NULL,watered=0 WHERE user_id=? AND plot_index=?',
                 [user_id, plot_index])
    conn.commit()
    coins = conn.execute('SELECT coins FROM users WHERE id=?', [user_id]).fetchone()['coins']
    conn.close()
    return jsonify({'ok':True,'msg':f'收获{crop["name"]}，+{crop["value"]}金币！','coins':coins,'value':crop['value']})

@app.route('/api/steal', methods=['POST'])
def steal():
    """偷菜：只能偷成熟作物，收益50%，每块地只能偷一次"""
    data = request.json
    thief_id, owner_id, plot_index = data['thief_id'], data['owner_id'], data['plot_index']
    if thief_id == owner_id:
        return jsonify({'ok':False,'msg':'不能偷自己的菜'})
    conn = get_db()
    plot = conn.execute('SELECT * FROM plots WHERE user_id=? AND plot_index=?', [owner_id, plot_index]).fetchone()
    if not plot or not plot['crop_type']:
        conn.close()
        return jsonify({'ok':False,'msg':'没有作物可偷'})
    now = time.time()
    if now - plot['plant_time'] < plot['grow_seconds']:
        conn.close()
        return jsonify({'ok':False,'msg':'还没熟呢'})
    crop = CROPS.get(plot['crop_type'], {})
    steal_value = int(crop['value'] * 0.5)
    conn.execute('UPDATE users SET coins=coins+? WHERE id=?', [steal_value, thief_id])
    conn.execute('UPDATE plots SET crop_type=NULL,plant_time=NULL,grow_seconds=NULL,watered=0 WHERE user_id=? AND plot_index=?',
                 [owner_id, plot_index])
    conn.commit()
    coins = conn.execute('SELECT coins FROM users WHERE id=?', [thief_id]).fetchone()['coins']
    owner_name = conn.execute('SELECT username FROM users WHERE id=?', [owner_id]).fetchone()['username']
    conn.close()
    return jsonify({'ok':True,'msg':f'偷了{owner_name}的{crop["name"]}，+{steal_value}金币！','coins':coins,'value':steal_value})

@app.route('/api/users')
def list_users():
    conn = get_db()
    users = conn.execute('SELECT id,username,coins FROM users ORDER BY coins DESC').fetchall()
    conn.close()
    return jsonify({'ok':True,'users':[dict(u) for u in users]})

@app.route('/api/rank')
def rank():
    conn = get_db()
    users = conn.execute('SELECT id,username,coins FROM users ORDER BY coins DESC').fetchall()
    conn.close()
    return jsonify({'ok':True,'rank':[dict(u) for u in users]})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 6789))
    app.run(host='0.0.0.0', port=port, debug=False)
