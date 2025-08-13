import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import sqlite3
from typing import List
from dotenv import load_dotenv

import asyncio
import json

load_dotenv()

DEFAULT_PATH =  os.path.join("/", "home", "blarp", "storage", "roa2-lb", "leaderboard.sqlite3")
DB_PATH = os.environ.get("SQLITE_DB_PATH", DEFAULT_PATH)
    
print(f"{DB_PATH}, {os.path.exists(DB_PATH)}")

if not os.path.exists(DB_PATH):
    DB_PATH = DEFAULT_PATH

print(f"{DB_PATH}, {os.path.exists(DB_PATH)}")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.1.30:8006", "http://192.168.1.30:8007"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Example endpoint using sqlite3 dependency
from fastapi import Depends

@app.get("/matches")
@app.get("/matches/{mevsrat}")
def get_players(db: sqlite3.Connection = Depends(get_db), mevsrat: int = -1):
    cursor = db.cursor()
    if mevsrat < 0:
        cursor.execute("SELECT * FROM entries_vw LIMIT 1000")
    else:
        cursor.execute("select * from entries_vw WHERE steamid in (76561197990353168, 76561198089674311)")
    rows = cursor.fetchall()
    return {"entries": rows}

@app.get("/lb-info")
def get_lb_info(db: sqlite3.Connection = Depends(get_db)):
    cur = db.cursor()
    query = """
        WITH player_days AS (
            SELECT
                e.leaderboard_id,
                e.steamid,
                COUNT(DISTINCT date(e.snapshot_time)) AS days_active,
                MAX(e.rating) AS latest_rating
            FROM entries_vw e
            WHERE date(e.snapshot_time) >= date('now', '-30 day') -- last 30 days
            GROUP BY e.leaderboard_id, e.steamid
        ),
        player_with_rank AS (
            SELECT
                p.leaderboard_id,
                p.steamid,
                p.days_active,
                r.rank_name,
                r.rank_display
            FROM player_days p
            JOIN ranks r
            ON p.latest_rating BETWEEN r.rank_min AND r.rank_max
        ),
        rank_summary AS (
            SELECT
                leaderboard_id,
                rank_display,
                COUNT(DISTINCT steamid) AS total_players,
                COUNT(DISTINCT CASE WHEN days_active >= 5 THEN steamid END) AS active_players
            FROM player_with_rank
            GROUP BY leaderboard_id, rank_display
        )
        SELECT *
        FROM rank_summary
        ORDER BY leaderboard_id, rank_display;
    """
    cur.execute(query)
    headers = [desc[0] for desc in cur.description]
    return {"data": [dict(zip(headers, row)) for row in cur.fetchall()]}