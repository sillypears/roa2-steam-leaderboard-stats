import os
import xml.etree.ElementTree as et

import requests
import pandas as pd
from utils.utils import rivals2_plot, rivals2_line_plot, generate_leaderboard

XML_CACHE = './cache/xml/'
DF_CACHE = './cache/df.pkl'

# Rivals 2, ranked lite ids
GAME_ID = '2217000'
LEADERBOARD_ID = '14800950'


def download_xml():
    """
    Download and save each xml file provided by the steam xml api
    """
    next_url = f'https://steamcommunity.com/stats/{GAME_ID}/leaderboards/{LEADERBOARD_ID}/?xml=1'

    while next_url is not None:
        xml_raw = requests.get(next_url).text
        xml = et.fromstring(xml_raw)

        start = xml.find('entryStart').text.strip()
        end = xml.find('entryEnd').text.strip()

        with open(f'{XML_CACHE}/{start}-{end}.xml', 'w') as file:
            file.write(xml_raw)
            print(f'saved {file.name}')

        next_url = xml.find("nextRequestURL").text.strip() if xml.find("nextRequestURL") is not None else None


def get_leaderboard_xml():
    """
    If leaderboard xml does not exist, download it
    """
    os.makedirs(os.path.dirname(XML_CACHE), exist_ok=True)
    if len(os.listdir(XML_CACHE)) == 0:
        download_xml()


def xml_to_df():
    """
    Return a dataframe of leaderboard entrants from all xml files
    """
    get_leaderboard_xml()

    all_dfs = []
    for file_name in os.listdir(XML_CACHE):
        file_path = os.path.join(XML_CACHE, file_name)
        df = pd.read_xml(file_path, xpath='.//entry')
        all_dfs.append(df)

    return pd.concat(all_dfs, ignore_index=True)


def get_leaderboard_df():
    """
    Find the leaderboard df in cache, or create a new one
    """

    if os.path.exists(DF_CACHE):
        return pd.read_pickle(DF_CACHE)

    df = xml_to_df()
    df.to_pickle(DF_CACHE)
    print(f'saved {DF_CACHE}')
    return df


if __name__ == '__main__':
    df = get_leaderboard_df()
    rivals2_plot(df)
    rivals2_line_plot(df)
    generate_leaderboard(df)
