import sqlite3
from datetime import datetime

DB_PATH = 'leaderboard.sqlite3'

def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS leaderboards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            leaderboard_id TEXT,
            name TEXT,
            display_name TEXT
        );
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            steamid TEXT,
            rating INTEGER,
            rank INTEGER,
            leaderboard_id INTEGER,
            snapshot_time DATETIME,
            FOREIGN KEY (leaderboard_id) REFERENCES leaderboards(id)
        );
    ''')
    conn.commit()
    return conn

def get_leaderboard_by_name(conn, name):
    cur = conn.cursor()
    cur.execute('SELECT id FROM leaderboards WHERE name = ?', (name,))
    return cur.fetchone()

def get_leaderboard_by_id(conn, leaderboard_id):
    cur = conn.cursor()
    cur.execute('SELECT id FROM leaderboards WHERE leaderboard_id = ?', (leaderboard_id,))
    return cur.fetchone()

def save_leaderboard(conn, leaderboard_id, name, display_name):
    if not get_leaderboard_by_name(conn, name): 
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO leaderboards (leaderboard_id, name, display_name)
            VALUES (?, ?, ?)
        ''', (leaderboard_id, name, display_name))
        conn.commit()
        return cur.lastrowid
    
def save_entries(conn, leaderboard_id, entries, snapshot_time=None):
    if snapshot_time is None:
        snapshot_time = datetime.now(datetime.timezone.utc).isoformat()

    cur = conn.cursor()
    for steamid, rating, rank in entries:
        cur.execute('''
            INSERT INTO entries (steamid, rating, rank, leaderboard_id, snapshot_time)
            VALUES (?, ?, ?, ?, ?)
        ''', (steamid, rating, rank, leaderboard_id, snapshot_time))
    conn.commit()

def save_entries_bulk(conn, entries):
    """
    entries: list of tuples (steamid, rating, rank, leaderboard_id, snapshot_time)
    """
    cur = conn.cursor()
    cur.executemany('''
        INSERT INTO entries (steamid, rating, rank, leaderboard_id, snapshot_time)
        VALUES (?, ?, ?, ?, ?)
    ''', entries)
    conn.commit()