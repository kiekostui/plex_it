import requests
import json
import urllib.parse
import sys
import uuid
import os
import xml.etree.ElementTree as ET
from datetime import datetime, date, timedelta, timezone

# --- Configuration Constants ---

REGION = os.environ.get('REGION')
DAYS = 3

ip = REGION
print(ip)


# --- API request for epg data  ---

def get_epg_data(date_string):

    client_uiid = str(uuid.uuid4())
    page_load_id = str(uuid.uuid4())
    
    HEADERS = {
        'Accept':'application/json',
        'Accept-Language':'it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7',
        'Origin': 'https://watch.plex.tv',
        'Referer': 'https://watch.plex.tv/',
        'X-Plex-Client-Identifier':f'{client_uiid}',
        'X-Plex-Product': 'Plex Mediaverse',
        'X-Plex-Provider-Version': '6.5.0',
        'X-Forwarded-For':f'{REGION}'
        }
    
    luma_url_parts = ['https://watch.plex.tv/it/api/luma?',
                     'lumaCache=always-static',
                     '&url=https%253A%252F%252Fluma.plex.tv%252Fapi%252Ffragment%252Flive-tv%252Fcategory',
                     '%253Fmetrics.page%253Dlive-tv.guide',
                     f'%2526metrics.pageLoadID%253D{page_load_id}',
                     '%2526screen.type%253DCustom',
                     '%2526key%253D%25252Flineups%25252Fplex%25252Fchannels',
                     '%25253Fgenre%25253D',
                     f'%2526startDate%253D{date_string}'
                     ]
    
    luma_url = ''.join(luma_url_parts)
    
    print (f'epg request for: {date_string}')
    
    try: 
        luma_response = requests.post(luma_url, headers=HEADERS, timeout=30)
        luma_response.raise_for_status()
        
    except requests.exceptions.RequestException as e:
        print (f'Response error: {e}')
        if 'luma_response' in locals() and hasattr(luma_response, 'text'):
            print(f'Server response: {luma_response.text[:200]}...')
        
        return None
        
    try:
        epg_data = luma_response.json()
        
    except:
        print('Response is not a valid json')
        return None
    
    return epg_data
    

# --- Time Conversion Function (from timestamp to epg string) ---

def convert_date(date_timestamp):
    
    try:
        date_obj = datetime.fromtimestamp(date_timestamp, tz=timezone.utc)
    except:
        return ''
    
    date_string = date_obj.strftime('%Y%m%d%H%M%S +0000')
    
    return date_string
    
    
# --- Data extractions: retruns dictionary with id channels as keys and all channels and programmes data as values ---

def extract_data(epg_json):
    
    channels_dict = {}
    
    print('Parsing json Response')
    
    for element in epg_json:
        ch_id = element.get('id', '')
        if not ch_id:
            continue
        ch_name = element.get('title', 'No Name')
        ch_icon = element.get('thumb', '')
        ch_programmes = element.get('airings', [])
        
        channels_dict[ch_id] ={
        'name':ch_name,
        'icon':ch_icon,
        'programmes':[]
        }
        
        for programme in ch_programmes:
            prog_title = programme.get('title','')
            prog_start_timestamp = programme.get('data', {}).get('beginsAt',None)
            prog_stop_timestamp = programme.get('data', {}).get('endsAt',None)
            if not (prog_start_timestamp and prog_stop_timestamp):
                continue
            prog_start = convert_date(prog_start_timestamp)
            prog_stop = convert_date(prog_stop_timestamp)
            if not (prog_start and prog_stop):
                continue
            prog_icon = programme.get('previewData', {}).get('background',{}).get('image', {}).get('url', '')
            prog_desc = programme.get('previewData', {}).get('summary', '')
            
            prog_dict ={
            'start':prog_start,
            'stop': prog_stop,
            'channel':ch_id,
            'title':prog_title,
            'desc':prog_desc,
            'icon':prog_icon
            }
            
            channels_dict[ch_id]['programmes'].append(prog_dict)
        
        #channels_dict['channel_id'] = ch_dict
        
    return channels_dict     
        


# --- convert json data to xml epg formatted  ---

def json_to_xml(json_data):
    
    print('Parsing json master e creating xml epg')
    
    epg_xml = ET.Element('tv')
    epg_xml.attrib['source-info-name'] = 'None'
    
    #first iteration to append 'channel' elements    
    for channel_id in json_data:
        channel_xml = ET.SubElement(epg_xml, 'channel', id= channel_id)
        name_xml = ET.SubElement(channel_xml, 'display-name')
        name_xml.text = json_data[channel_id]['name']
        icon_xml = ET.SubElement(channel_xml, 'icon', src= json_data[channel_id]['icon'])
        
    #second iteration to append 'programme' elements
    for channel_id in json_data:
        for programme in json_data[channel_id]['programmes']:
            programme_xml = ET.SubElement(epg_xml, 'programme', start=programme['start'], stop=programme['stop'], channel=channel_id )
            title_xml = ET.SubElement(programme_xml, 'title')
            title_xml.text = programme['title']
            desc_xml = ET.SubElement(programme_xml, 'desc')
            desc_xml.text = programme['desc']
            icon_xml = ET.SubElement(programme_xml, 'icon', src=programme['icon'])
            
    return epg_xml
    
    


date_request = date.today()

time_delta = timedelta(days=1)

epg_master_json = {}

channels_list = []


for d in range(1, DAYS + 1):
      
    day_string = date_request.isoformat()
    
    epg_json = get_epg_data(day_string)
    
    if not epg_json:
        continue
    
    epg_part_json = extract_data(epg_json)
    
    extracted_channels = list(epg_part_json)
    
    print('Append data to json master')
    
    for channel_id in extracted_channels:
        if not channel_id in channels_list:
            channels_list.append(channel_id)
            
            epg_master_json[channel_id] = {
            'name':epg_part_json[channel_id]['name'],
            'icon': epg_part_json[channel_id]['icon'],
            'programmes':[]
            }
        
        epg_master_json[channel_id]['programmes'].extend(epg_part_json[channel_id]['programmes'])
    
    date_request = date_request + time_delta
    
    #with open('epg_master.json', 'w') as outfile:
        #json.dump(epg_master_json, outfile, indent=4)
        
epg_xml = json_to_xml(epg_master_json)
    
tree = ET.ElementTree(epg_xml)
ET.indent(tree, space='    ', level=0)

print('Writng epg to File')
    
tree.write('epg_plex_it.xml', encoding='utf-8', xml_declaration=True)
        
