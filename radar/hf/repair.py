import sqlite3
src = sqlite3.connect('/home/box/hf-radar/db.sqlite.broken')
dst = sqlite3.connect('/home/box/hf-radar/db.sqlite')
dst.execute('CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT)')
dst.execute('CREATE TABLE models(date TEXT NOT NULL, id TEXT, downloads TEXT, likes TEXT, createdAt TEXT, lastModified TEXT, pipeline_tag TEXT, library_name TEXT, license TEXT, tags TEXT, author TEXT, PRIMARY KEY(date, id))')
dst.execute('CREATE TABLE datasets(date TEXT NOT NULL, id TEXT, downloads TEXT, likes TEXT, createdAt TEXT, lastModified TEXT, tags TEXT, author TEXT, PRIMARY KEY(date, id))')
dst.execute('CREATE TABLE spaces(date TEXT NOT NULL, id TEXT, likes TEXT, createdAt TEXT, lastModified TEXT, tags TEXT, author TEXT, runtime TEXT, PRIMARY KEY(date, id))')
for t in ['meta','models','datasets']:
    rows = src.execute('SELECT * FROM ' + t).fetchall()
    if rows:
        ph = ','.join('?' * len(rows[0]))
        dst.executemany('INSERT INTO ' + t + ' VALUES (' + ph + ')', rows)
    print(t, 'copied', len(rows))
dst.commit()
for t in ['meta','models','datasets','spaces']:
    print(t, dst.execute('SELECT COUNT(*) FROM ' + t).fetchone()[0])
ck = dst.execute("SELECT value FROM meta WHERE key='checkpoint_spaces'").fetchone()
print('CHECKPOINT:', (ck[0][:70] if ck and ck[0] else 'NONE'))
