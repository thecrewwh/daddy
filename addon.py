# -*- coding: utf-8 -*-
'''
***********************************************************
*
* @file addon.py
* @package script.module.thecrew
*
* Created on 2024-03-08.
* Copyright 2024 by The Crew. All rights reserved.
*
* @license GNU General Public License, version 3 (GPL-3.0)
*
********************************************************cm*
'''
# pylint: disable-msg=F0401

import re
import os
import sys
import json
import html
import base64
import time
import requests
import xbmc
import xbmcvfs
import xbmcgui
import xbmcplugin
import xbmcaddon
from datetime import datetime, timezone
from urllib.parse import urlencode, quote, unquote, parse_qsl, quote_plus, urlparse

addon_url = sys.argv[0]
addon_handle = int(sys.argv[1])
params = dict(parse_qsl(sys.argv[2][1:]))
addon = xbmcaddon.Addon(id='plugin.video.daddylive')

mode = addon.getSetting('mode')
BASE_SEED = ''
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36'
_base_cache = None
json_url = 'stream/stream-%s.php'
schedule_rel = 'schedule/schedule-generated.php'
FANART = addon.getAddonInfo('fanart')
ICON = addon.getAddonInfo('icon')

def get_active_base():
    global _base_cache
    if _base_cache:
        return _base_cache
    try:
        r = requests.get(BASE_SEED, headers={'User-Agent': UA}, timeout=10, allow_redirects=True)
        p = urlparse(r.url)
        _base_cache = f'{p.scheme}://{p.netloc}/'
    except:
        _base_cache = BASE_SEED if BASE_SEED.endswith('/') else BASE_SEED + '/'
    return _base_cache

def url_from_base(path):
    b = get_active_base()
    if path.startswith('/'):
        path = path[1:]
    return b + path

def log(msg):
    LOGPATH = xbmcvfs.translatePath('special://logpath/')
    FILENAME = 'daddylive.log'
    LOG_FILE = os.path.join(LOGPATH, FILENAME)
    try:
        if isinstance(msg, str):
            _msg = f'\n    {msg}'
        else:
            raise TypeError('log() msg not of type str!')
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'w', encoding='utf-8'):
                pass
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            line = ('[{} {}]: {}').format(datetime.now().date(), str(datetime.now().time())[:8], _msg)
            f.write(line.rstrip('\r\n') + '\n')
    except:
        pass

def get_local_time(utc_time_str):
    try:
        utc_now = datetime.utcnow()
        event_time_utc = datetime.strptime(utc_time_str, '%H:%M')
        event_time_utc = event_time_utc.replace(year=utc_now.year, month=utc_now.month, day=utc_now.day)
        event_time_utc = event_time_utc.replace(tzinfo=timezone.utc)
        local_time = event_time_utc.astimezone()
        time_format_pref = addon.getSetting('time_format')
        if time_format_pref == '1':
            return local_time.strftime('%H:%M')
        else:
            return local_time.strftime('%I:%M %p').lstrip('0')
    except:
        return utc_time_str

def build_url(query):
    return addon_url + '?' + urlencode(query)

def addDir(title, dir_url, is_folder=True):
    li = xbmcgui.ListItem(title)
    labels = {'title': title, 'plot': title, 'mediatype': 'video'}
    if getKodiversion() < 20:
        li.setInfo("video", labels)
    else:
        infotag = li.getVideoInfoTag()
        infotag.setMediaType(labels.get("mediatype", "video"))
        infotag.setTitle(labels.get("title", "Daddylive"))
        infotag.setPlot(labels.get("plot", labels.get("title", "Daddylive")))
    li.setArt({'thumb': '', 'poster': '', 'banner': '', 'icon': ICON, 'fanart': FANART})
    li.setProperty("IsPlayable", 'false' if is_folder else 'true')
    xbmcplugin.addDirectoryItem(handle=addon_handle, url=dir_url, listitem=li, isFolder=is_folder)

def closeDir():
    xbmcplugin.endOfDirectory(addon_handle)

def getKodiversion():
    try:
        return int(xbmc.getInfoLabel("System.BuildVersion")[:2])
    except:
        return 18

def Main_Menu():
    menu = [
        ['[B][COLOR gold]LIVE SPORTS SCHEDULE[/COLOR][/B]', 'sched'],
        ['[B][COLOR gold]LIVE TV CHANNELS[/COLOR][/B]', 'live_tv'],
        ['[B][COLOR gold]SEARCH EVENTS SCHEDULE[/COLOR][/B]', 'search'],
        ['[B][COLOR gold]SEARCH LIVE TV CHANNELS[/COLOR][/B]', 'search_channels'],
        ['[B][COLOR gold]REFRESH CATEGORIES[/COLOR][/B]', 'refresh_sched']
    ]
    for m in menu:
        addDir(m[0], build_url({'mode': 'menu', 'serv_type': m[1]}))
    closeDir()

def getCategTrans():
    hea = {'User-Agent': UA, 'Referer': get_active_base(), 'Origin': get_active_base()}
    categs = []
    try:
        schedule_url = url_from_base(schedule_rel)
        schedule = requests.get(schedule_url, headers=hea, timeout=10).json()
        for _, events in schedule.items():
            for categ, events_list in events.items():
                categs.append((categ.replace('</span>', ''), json.dumps(events_list)))
    except:
        xbmcgui.Dialog().ok("Error", "Error fetching category data.")
        return []
    return categs

def Menu_Trans():
    categs = getCategTrans()
    if not categs:
        return
    for categ_name, events_list in categs:
        addDir(categ_name, build_url({'mode': 'showChannels', 'trType': categ_name}))
    closeDir()

def ShowChannels(categ, channels_list):
    for item in channels_list:
        title = item.get('title')
        addDir(title, build_url({'mode': 'trList', 'trType': categ, 'channels': json.dumps(item.get('channels'))}), True)
    closeDir()

def getTransData(categ):
    trns = []
    categs = getCategTrans()
    for categ_name, events_list_json in categs:
        if categ_name == categ:
            events_list = json.loads(events_list_json)
            for item in events_list:
                event = item.get('event')
                time_str = item.get('time')
                event_time_local = get_local_time(time_str)
                title = f'[COLOR gold]{event_time_local}[/COLOR] {event}'
                channels = item.get('channels')
                if isinstance(channels, list) and all(isinstance(channel, dict) for channel in channels):
                    trns.append({
                        'title': title,
                        'channels': [{'channel_name': c.get('channel_name'), 'channel_id': c.get('channel_id')} for c in channels]
                    })
    return trns

def TransList(categ, channels):
    for channel in channels:
        channel_title = html.unescape(channel.get('channel_name'))
        channel_id = channel.get('channel_id')
        addDir(channel_title, build_url({'mode': 'trLinks', 'trData': json.dumps({'channels': [{'channel_name': channel_title, 'channel_id': channel_id}]})}), False)
    closeDir()

def getSource(trData):
    data = json.loads(unquote(trData))
    channels_data = data.get('channels')
    if channels_data and isinstance(channels_data, list):
        url_stream = url_from_base(json_url % channels_data[0]["channel_id"])
        xbmcplugin.setContent(addon_handle, 'videos')
        PlayStream(url_stream)

def list_gen():
    chData = channels()
    for c in chData:
        addDir(c[1], build_url({'mode': 'play', 'url': url_from_base(c[0])}), False)
    closeDir()

def channels():
    url = url_from_base('/24-7-channels.php')
    do_adult = xbmcaddon.Addon().getSetting('adult_pw')
    hea = {'Referer': get_active_base(), 'user-agent': UA}
    resp = requests.post(url, headers=hea).text
    ch_block = re.findall('<center><h1(.+?)tab-2', resp, re.DOTALL)
    chan_data = re.findall('href="(.*?)" target.*?<strong>(.*?)</strong>', ch_block[0])
    channels = []
    for href, title in chan_data:
        if "18+" not in title:
            channels.append([href, title])
        if do_adult == 'lol' and "18+" in title:
            channels.append([href, title])
    return channels

def PlayStream(link):
    try:
        headers = {'User-Agent': UA, 'Referer': get_active_base(), 'Origin': get_active_base()}
        response = requests.get(link, headers=headers, timeout=10).text

        if 'wikisport.best' in response:
            for _ in range(3):
                iframes = re.findall(r'iframe src="([^"]*)', response)
                if not iframes:
                    return
                url2 = iframes[0]
                headers['Referer'] = headers['Origin'] = url2
                response = requests.get(url2, headers=headers, timeout=10).text
        else:
            iframes = re.findall(r'<a[^>]*href="([^"]+)"[^>]*>\s*<button[^>]*>\s*Player\s*2\s*</button>', response)
            if not iframes:
                return
            url2 = url_from_base(iframes[0].replace('//cast', '/cast'))
            headers['Referer'] = headers['Origin'] = url2
            response = requests.get(url2, headers=headers, timeout=10).text

            iframe_match = re.search(r'iframe src="([^"]*)', response)
            if not iframe_match:
                return
            url2 = iframe_match.group(1)
            headers['Referer'] = headers['Origin'] = url2
            response = requests.get(url2, headers=headers, timeout=10).text

        ck_match = re.search(r'const\s+CHANNEL_KEY\s*=\s*"([^"]+)"', response)
        bundle_match = re.search(r'const\s+XJZ\s*=\s*"([^"]+)"', response)
        if not ck_match or not bundle_match:
            return
        channel_key = ck_match.group(1)
        bundle = bundle_match.group(1)
        parts = json.loads(base64.b64decode(bundle).decode("utf-8"))
        for k, v in parts.items():
            parts[k] = base64.b64decode(v).decode("utf-8")
        host_array_match = re.search(r"host\s*=\s*\[([^\]]+)\]", response)
        if host_array_match:
            host_parts = [part.strip().strip("'\"") for part in host_array_match.group(1).split(',')]
            host = ''.join(host_parts)
        else:
            return
        bx = [40, 60, 61, 33, 103, 57, 33, 57]
        sc = ''.join(chr(b ^ 73) for b in bx)
        auth_url = f'{host}{sc}?channel_id={quote_plus(channel_key)}&ts={quote_plus(parts["b_ts"])}&rnd={quote_plus(parts["b_rnd"])}&sig={quote_plus(parts["b_sig"])}'
        server_lookup_match = re.findall(r'fetchWithRetry\(\s*\'([^\']*)', response)
        if not server_lookup_match:
            return
        server_lookup = server_lookup_match[0]
        requests.get(auth_url, headers=headers, timeout=10)
        server_lookup_url = f"https://{urlparse(url2).netloc}{server_lookup}{channel_key}"
        response = requests.get(server_lookup_url, headers=headers, timeout=10).json()
        server_key = response.get('server_key')
        if not server_key:
            return
        host_raw = f'https://{urlparse(url2).netloc}'
        if server_key == "top1/cdn":
            m3u8 = f"https://top1.newkso.ru/top1/cdn/{channel_key}/mono.m3u8"
        else:
            m3u8 = f"https://{server_key}new.newkso.ru/{server_key}/{channel_key}/mono.m3u8"
        m3u8 += f'|Referer={host_raw}/&Origin={host_raw}&Connection=Keep-Alive&User-Agent={quote_plus(UA)}'
        if not xbmc.getCondVisibility('System.HasAddon(inputstream.ffmpegdirect)'):
            xbmcgui.Dialog().ok("Missing InputStream", "This stream requires the 'inputstream.ffmpegdirect' addon.")
            return
        liz = xbmcgui.ListItem('Daddylive', path=m3u8)
        liz.setProperty('inputstream', 'inputstream.ffmpegdirect')
        liz.setMimeType('application/x-mpegURL')
        liz.setProperty('inputstream.ffmpegdirect.is_realtime_stream', 'true')
        liz.setProperty('inputstream.ffmpegdirect.stream_mode', 'timeshift')
        liz.setProperty('inputstream.ffmpegdirect.manifest_type', 'hls')
        xbmcplugin.setResolvedUrl(addon_handle, True, liz)
    except:
        import traceback
        log(f"Error in PlayStream: {traceback.format_exc()}")

def Search_Events():
    keyboard = xbmcgui.Dialog().input("Enter search term", type=xbmcgui.INPUT_ALPHANUM)
    if not keyboard or keyboard.strip() == '':
        return
    term = keyboard.lower()
    results = []
    categs = getCategTrans()
    for categ_name, events_list_json in categs:
        events_list = json.loads(events_list_json)
        for item in events_list:
            event_title = item.get('event', '')
            if term in event_title.lower():
                time_str = item.get('time')
                event_time_local = get_local_time(time_str)
                title = f'[COLOR gold]{event_time_local}[/COLOR] {event_title}'
                channels = item.get('channels', [])
                results.append({'title': title, 'channels': channels})
    if not results:
        xbmcgui.Dialog().ok("Search", "No matching events found.")
        return
    for result in results:
        addDir(result['title'], build_url({'mode': 'trList', 'trType': 'search', 'channels': json.dumps(result['channels'])}), True)
    closeDir()

def Search_Channels():
    keyboard = xbmcgui.Dialog().input("Enter channel name", type=xbmcgui.INPUT_ALPHANUM)
    if not keyboard or keyboard.strip() == '':
        return
    term = keyboard.lower()
    results = []
    categs = getCategTrans()
    for categ_name, events_list_json in categs:
        events_list = json.loads(events_list_json)
        for item in events_list:
            for channel in item.get('channels', []):
                name = channel.get('channel_name', '')
                if term in name.lower():
                    title = html.unescape(name)
                    results.append({
                        'title': title,
                        'channel_id': channel.get('channel_id')
                    })
    if not results:
        xbmcgui.Dialog().ok("Search", "No matching channels found.")
        return
    for result in results:
        addDir(result['title'], build_url({
            'mode': 'trLinks',
            'trData': json.dumps({'channels': [{'channel_name': result["title"], 'channel_id': result["channel_id"]}]})
        }), False)
    closeDir()

if not mode:
    Main_Menu()
else:
    if mode == 'menu':
        servType = params.get('serv_type')
        if servType == 'sched':
            Menu_Trans()
        elif servType == 'live_tv':
            list_gen()
        elif servType == 'search':
            Search_Events()
        elif servType == 'search_channels':
            Search_Channels()
        elif servType == 'refresh_sched':
            xbmc.executebuiltin('Container.Refresh')
    elif mode == 'showChannels':
        transType = params.get('trType')
        channels = getTransData(transType)
        ShowChannels(transType, channels)
    elif mode == 'trList':
        transType = params.get('trType')
        channels = json.loads(params.get('channels'))
        TransList(transType, channels)
    elif mode == 'trLinks':
        trData = params.get('trData')
        getSource(trData)
    elif mode == 'play':
        link = params.get('url')
        PlayStream(link)
