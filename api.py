import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import sqlite3
import aiomysql
from typing import List, Dict, Any
from dotenv import load_dotenv
import json
import threading
from contextlib import contextmanager
load_dotenv()

DEFAULT_PATH =  os.path.join("/", "home", "blarp", "storage", "roa2-lb", "leaderboard.sqlite3")
DB_PATH = os.environ.get("SQLITE_DB_PATH", DEFAULT_PATH)

print(f"{DB_PATH}, {os.path.exists(DB_PATH)}")

if not os.path.exists(DB_PATH):
    DB_PATH = DEFAULT_PATH

print(f"{DB_PATH}, {os.path.exists(DB_PATH)}")


# Create a thread-local storage for connections
thread_local = threading.local()

def get_db_connection():
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    return thread_local.connection

@contextmanager
def get_db():
    conn = get_db_connection()
    try:
        yield conn
    finally:
        # Don't close the connection, keep it for the thread
        pass

@asynccontextmanager
async def lifespan(app: FastAPI) -> Any:
    pool = await aiomysql.create_pool(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASS"),
        db=os.environ.get("DDB_SCHEMA") if os.environ.get(
            "DEBUG") else os.environ.get("DB_SCHEMA"),
        autocommit=True,
    )
    app.state.db_pool = pool
    try:
        yield
    finally:
        pool.close()
        await pool.wait_closed()


async def safe_db_fetch_all(request: Request, query: str, params: tuple = ()) -> Dict[str, Any]:
    """Safe database fetch with proper error handling - uses request.app.state.db_pool"""
    try:
        async with request.app.state.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                rows = await cur.fetchall()
                return rows
    except Exception as e:
        raise Exception(f"Failed to fetch data: {str(e)}")

async def safe_db_fetch_one(request: Request, query: str, params: tuple = ()) -> Dict[str, Any]:
    """Safe database fetch one with proper error handling"""
    try:
        async with request.app.state.db_pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(query, params)
                row = await cur.fetchone()
                return row
    except Exception as e:
        raise Exception(f"Failed to fetch data: {str(e)}")


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://192.168.1.30:8006", "http://192.168.1.30:8007"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Depends

@app.get("/matches")
@app.get("/matches/{mevsrat}")
async def get_players(db: sqlite3.Connection = Depends(get_db_connection), mevsrat: int = -1):
    cursor = db.cursor()
    if mevsrat < 0:
        cursor.execute("SELECT * FROM entries_vw LIMIT 1000")
    else:
        cursor.execute("select * from entries_vw WHERE steamid in (76561197990353168, 76561198089674311)")
    headers = [desc[0] for desc in cursor.description]
    return {"data": [dict(zip(headers, row)) for row in cursor.fetchall()]}

@app.get("/player/{steam_id}")
async def get_player_by_steam_id(db: sqlite3.Connection = Depends(get_db_connection), steam_id: int = -1):
    if steam_id < 0: 
        return {"data": [], "message": "Not a valid SteamID"}
    query = """
        SELECT 
            *
        FROM 
            entries_vw
        WHERE
            steamid = %s    
    """ % (steam_id)
    cur = db.cursor()
    cur.execute(query)
    headers = [desc[0] for desc in cur.description]
    return {"data": [dict(zip(headers, row)) for row in cur.fetchall()]}

@app.get("/lb-info")
async def get_lb_info(db: sqlite3.Connection = Depends(get_db_connection)):

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


@app.get("/get_steamid/{name}")
async def get_steamid_by_name(req: Request, name: str = None):
    if name == None: return {"data": [], "message": "No valid name given"}

    query = f"""
        SELECT 
            JSON_EXTRACT(linked_accounts, '$') as linked_accounts
        FROM 
            leaderboard.player_vw
        WHERE
            display_name LIKE "%%{name}%%"
    """
    data = await safe_db_fetch_all(request=req, query=query)
    result = []
    for row in data:
        try:
            accounts = json.loads(row['linked_accounts'])
            for account in accounts:
                if account.get('platform') == 'Steam':
                    result.append({
                        'steam_id': account.get('platform_user_id'),
                        'steam_username': account.get('username'),
                        'display_name': name
                    })
                    break  # Found Steam account, no need to continue
                    
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Error parsing JSON for {name}: {e}")
            continue
    
    return {"data": result}

@app.get("/bother/{name}")
async def get_both_from_name(req: Request, name: str = None):
    try:
        data = await get_steamid_by_name(req, name)
    except Exception as e:
        print(e)
        return {"data": []}
    print(data)
    steamid = int(data['data'][0]['steam_id'])
    s_data = await get_player_by_steam_id(db=get_db_connection(), steam_id=steamid)
    return {"data": s_data, "steamid": steamid, "name": name}

@app.get("/bad-endpoint")
async def get_bad_info(req: Request, name: str = None):
    if name is None:
        return {"data": [], "message": "Give a name bozo"}

    query = '''
        SELECT p.*
        FROM leaderboard.player_vw p
        JOIN leaderboard.linked_accounts la ON p.player_id = la.player_id
        WHERE la.username = %s;
    '''
    rows = await safe_db_fetch_all(req, query, (name,))

    if rows:
        match_count_fields = [col for col in rows[0].keys() if col.endswith("_match_count")]

        updated_rows = []
        for row in rows:
            best_char, best_val = None, -1
            for field in match_count_fields:
                val = row[field]
                if val is not None and val > best_val:
                    best_char, best_val = field.replace("_match_count", ""), val

            # rebuild dict with desired insertion order
            new_row = {}
            for k, v in row.items():
                new_row[k] = v
                if k == "display_name":  # insert right after this field
                    new_row["most_played_character"] = {
                        "character": best_char,
                        "matches": best_val
                    }
            updated_rows.append(new_row)

        return updated_rows

    return rows
