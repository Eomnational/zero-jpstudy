from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import csv, io, json, os, sqlite3, time, urllib.parse

HERE = Path(__file__).resolve().parent
WORDS = json.loads((HERE / 'words.json').read_text())
WORD_IDS = {w['id'] for w in WORDS}
DB = HERE / 'progress.sqlite3'
TZ = ZoneInfo('Asia/Shanghai')

def today():
    return datetime.now(TZ).date().isoformat()

def connect():
    db = sqlite3.connect(DB)
    db.execute('CREATE TABLE IF NOT EXISTS progress (id TEXT PRIMARY KEY, state TEXT NOT NULL, reps INTEGER NOT NULL, due INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value INTEGER NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS review_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, word_id TEXT NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, result TEXT NOT NULL, at INTEGER NOT NULL)')
    return db

def settings(db):
    saved = dict(db.execute('SELECT key,value FROM settings'))
    return {'new_limit': saved.get('new_limit', 15), 'review_limit': saved.get('review_limit', 30)}

def daily_plan(db):
    day, now, cfg = today(), int(time.time()*1000), settings(db)
    rows = db.execute('SELECT id,due FROM progress').fetchall()
    progress = {r[0]:r[1] for r in rows}
    events = db.execute('SELECT word_id,kind,result FROM review_events WHERE day=?', (day,)).fetchall()
    new_done = {r[0] for r in events if r[1]=='new'}
    review_done = {r[0] for r in events if r[1]=='review'}
    new_queue = [w['id'] for w in WORDS if w['id'] not in progress][:max(0,cfg['new_limit']-len(new_done))]
    review_queue = [wid for wid,due in sorted(rows,key=lambda r:r[1]) if due<=now and wid not in review_done][:max(0,cfg['review_limit']-len(review_done))]
    return {'date':day,'settings':cfg,'new_done':len(new_done),'review_done':len(review_done),
            'correct':sum(r[2]=='good' for r in events),'attempts':len(events),
            'new_queue':new_queue,'review_queue':review_queue,'queue':review_queue+new_queue,
            'available_due':sum(due<=now for _,due in rows)}

def recap(db):
    end = datetime.now(TZ).date()
    days = [(end-timedelta(days=i)).isoformat() for i in range(13,-1,-1)]
    data = {d:{'date':d,'new':0,'review':0,'correct':0,'attempts':0} for d in days}
    rows = db.execute('SELECT day,kind,result,word_id FROM review_events WHERE day>=?', (days[0],)).fetchall()
    seen = set()
    for day,kind,result,wid in rows:
        if day not in data: continue
        item = data[day]
        item['attempts'] += 1
        item['correct'] += result=='good'
        if (day,kind,wid) not in seen:
            item[kind] += 1
            seen.add((day,kind,wid))
    return list(data.values())

EXPORT_HEADERS = ['日期','日语词形','假名读音','罗马音','中文意思','分类','学习类型','练习次数','正确次数','错误次数','最后一次结果','来源']
CAT_LABELS = {'O':'汉字联想','K':'训读和语','L':'外来语','F':'假名功能词'}

def export_rows(db, day):
    events = db.execute('SELECT word_id,kind,result,at FROM review_events WHERE day=? ORDER BY at,event_id',(day,)).fetchall()
    grouped = {}
    for wid,kind,result,at in events:
        entry = grouped.setdefault(wid,{'kinds':set(),'attempts':0,'correct':0,'last':'','at':at})
        entry['kinds'].add(kind)
        entry['attempts'] += 1
        entry['correct'] += result == 'good'
        entry['last'] = '记住了' if result == 'good' else '需再练'
    rows = []
    for w in WORDS:
        if w['id'] not in grouped: continue
        e = grouped[w['id']]
        kind = '新词+复习' if len(e['kinds']) > 1 else ('新词' if 'new' in e['kinds'] else '复习')
        rows.append([day,w['term'],w['reading'],w.get('romaji',''),w['meaning'],CAT_LABELS.get(w['cat'],'其他'),kind,e['attempts'],e['correct'],e['attempts']-e['correct'],e['last'],w.get('source','')])
    return rows

def export_csv(db, day):
    out = io.StringIO(newline='')
    writer = csv.writer(out)
    writer.writerow(EXPORT_HEADERS)
    for row in export_rows(db,day):
        # Keep Excel from evaluating user-supplied text as a formula.
        writer.writerow(["'"+v if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@')) else v for v in row])
    return ('\ufeff'+out.getvalue()).encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    def send(self, status, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', 'http://localhost:5173')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def send_csv(self, body, day):
        self.send_response(200)
        self.send_header('Content-Type','text/csv; charset=utf-8')
        self.send_header('Content-Disposition',f'attachment; filename=ZERO_jpstudy_{day}.csv')
        self.send_header('Access-Control-Allow-Origin','http://localhost:5173')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_OPTIONS(self): self.send(204, {})
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/words': return self.send(200, WORDS)
        if path == '/api/health': return self.send(200, {'ok':True,'words':len(WORDS)})
        with connect() as db:
            if path == '/api/progress':
                rows = db.execute('SELECT id,state,reps,due FROM progress').fetchall()
                return self.send(200, {r[0]:{'state':r[1],'reps':r[2],'due':r[3]} for r in rows})
            if path == '/api/plan': return self.send(200, daily_plan(db))
            if path == '/api/recap': return self.send(200, recap(db))
            if path == '/api/export/today.csv': return self.send_csv(export_csv(db,today()),today())
        self.send(404, {'error':'Not found'})
    def do_POST(self):
        try:
            n = int(self.headers.get('Content-Length','0'))
            data = json.loads(self.rfile.read(n))
            if self.path == '/api/settings':
                a,b = data['new_limit'],data['review_limit']
                if type(a) is not int or type(b) is not int or not (0<=a<=100 and 0<=b<=200): raise ValueError('Invalid limits')
                with connect() as db:
                    db.executemany('INSERT OR REPLACE INTO settings VALUES (?,?)',[('new_limit',a),('review_limit',b)])
                    plan = daily_plan(db)
                return self.send(200,plan)
            if self.path != '/api/review': return self.send(404, {'error':'Not found'})
            word_id, result = data['id'], data['result']
            if word_id not in WORD_IDS or result not in ('again','good'): raise ValueError('Invalid review')
            with connect() as db:
                row = db.execute('SELECT reps FROM progress WHERE id=?',(word_id,)).fetchone()
                kind = 'review' if row else 'new'
                reps = (row[0] if row else 0) + 1 if result == 'good' else 0
                due = int(time.time()*1000) + ([1,3,7,14,30][min(reps-1,4)]*86400000 if result == 'good' else 300000)
                state = 'mastered' if reps >= 5 else 'learning'
                db.execute('INSERT OR REPLACE INTO progress VALUES (?,?,?,?)',(word_id,state,reps,due))
                db.execute('INSERT INTO review_events (word_id,day,kind,result,at) VALUES (?,?,?,?,?)',(word_id,today(),kind,result,int(time.time()*1000)))
            self.send(200, {'id':word_id,'state':state,'reps':reps,'due':due})
        except (KeyError,ValueError,json.JSONDecodeError,TypeError): self.send(400, {'error':'Invalid request'})

if __name__ == '__main__':
    ThreadingHTTPServer(('127.0.0.1', int(os.getenv('PORT','8000'))), Handler).serve_forever()
