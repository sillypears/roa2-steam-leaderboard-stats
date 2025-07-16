import os, sys
import xml.etree.ElementTree as et
from xml.dom import minidom

import requests
import pandas as pd
from utils.utils import rivals2_plot, rivals2_line_plot, generate_leaderboard
from shutil import rmtree
import datetime
import db

DIRNAME = os.path.dirname(os.path.abspath(__file__))
FOLDER_CACHE = os.path.join(DIRNAME, "cache")
XML_CACHE = os.path.join(FOLDER_CACHE, "xml")
DF_CACHE = os.path.join(FOLDER_CACHE, 'df.pkl')

# Rivals 2, ranked lite ids
GAME_ID = '2217000'
LB_IDS = []

TOTAL = 0

def get_name_from_steamid(steamid: int) -> str:
    name = ""
    try:
        res = requests.get(f"https://steamcommunity.com/profiles/{int(steamid)}/?xml=1")
        res.raise_for_status()
    except:
        print(f"Steamid isn't an integer: {steamid}, {type(steamid)}")
        return name
    if  res.status_code == 200:
        print(f"Got name for {steamid}")
        xml_raw = res.text
        xml = et.fromstring(xml_raw)
        try:
            name = xml.find('steamID').text.strip()
        except:
            print(f"Couldn't find name in xml")
            print(xml)
            return ""
    return name

def download_xml():
    """
    Download and save each xml file provided by the steam xml api
    """
    conn = db.init_db()  
    lb_urls = f'https://steamcommunity.com/stats/{GAME_ID}/leaderboards/?xml=1'
    total = 0
    xml_raw = requests.get(lb_urls).text
    xml = et.fromstring(xml_raw)

    for lb in xml.findall('leaderboard'):
        try:
            LEADERBOARD_ID = int(lb.find("lbid").text.strip())
            LB_IDS.append(LEADERBOARD_ID)
            LEADERBOARD_NAME = lb.find("name").text.strip()
            LEADERBOARD_DNAME = lb.find("display_name").text.strip()
            lbid_id = db.save_leaderboard(conn, LEADERBOARD_ID, LEADERBOARD_NAME, LEADERBOARD_DNAME)
            if lbid_id is None:
                lbid_id = db.get_leaderboard_by_id(conn, leaderboard_id=LEADERBOARD_ID)[0]
        except ValueError:
            continue
        print(f'Processing leaderboard {LEADERBOARD_ID}:{LEADERBOARD_NAME}')
        os.makedirs(os.path.join(XML_CACHE, str(LEADERBOARD_ID)), exist_ok=True)
    for lbid in LB_IDS:
        try:
            if sys.argv[1]: lbid = LB_IDS[-1]
        except:
            pass
        next_url = f'https://steamcommunity.com/stats/{GAME_ID}/leaderboards/{lbid}/?xml=1'

        while next_url is not None:
            xml_raw = requests.get(next_url).text
            xml = et.fromstring(xml_raw)

            start = xml.find('entryStart').text.strip()
            end = xml.find('entryEnd').text.strip()
            if len(sys.argv) <= 1:
                with open(os.path.join(XML_CACHE, str(lbid), f"{lbid}-{start}-{end}.xml"), 'w') as file:
                    file.write(minidom.parseString(xml_raw).toprettyxml(indent="  "))
                    print(f'saved {file.name}')

            snapshot_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            batch = []
            for entry in xml.findall('entries/entry'):
                steamid = entry.find('steamid').text.strip()
                rating = int(entry.find('score').text.strip())
                rank = int(entry.find('rank').text.strip())
                steam_name = ""
                if steamid in (76561197990353168, 76561198089674311):
                    print(f"Getting name for {steamid}")
                    steam_name = get_name_from_steamid(steamid)
                batch.append((steamid, rating, rank, steam_name, db.get_leaderboard_by_id(conn, leaderboard_id=lbid)[0], snapshot_time))

            if batch:
                db.save_entries_bulk(conn, batch)
                total += len(batch)
            next_url_elem = xml.find("nextRequestURL")
            next_url = next_url_elem.text.strip() if next_url_elem is not None else None

    conn.close()
    return total

def get_leaderboard_xml():
    """
    If leaderboard xml does not exist, download it
    """
    os.makedirs(FOLDER_CACHE, exist_ok=True)
    total = 0
    if len(os.listdir(FOLDER_CACHE)) == 0:
        total = download_xml()
    return total

if __name__ == '__main__':
    try:
        rmtree(FOLDER_CACHE)
    except:
        pass
    TOTAL = get_leaderboard_xml()
    print(f"Saved {TOTAL} entries")
