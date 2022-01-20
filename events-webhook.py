from datetime import datetime
import base64
import json
import os
import pytz
import requests
import shutil
import tzlocal

session = requests.Session()
TIMEZONE = tzlocal.get_localzone()

with open('config.json', 'r') as of:
    config = json.load(of)

LAST_FILENAME = '.unvr-latest'
LAST_TOKENS = {}

try:
    with open(LAST_FILENAME, 'r') as of:
        LAST_TOKENS = json.load(of)
except FileNotFoundError:
    pass
except ValueError:
    pass

system_r = session.get(f"https://{config['unvr']['hostname']}/api/system", verify=config['unvr']['verify_tls'])

if system_r.status_code != 200:
    raise Exception(f"Received {system_r.status_code} on GET /api/system: {system_r.json()}")

session.headers.update({
    "X-CSRF-Token": system_r.headers['X-CSRF-Token']
})

login_r = session.post(f"https://{config['unvr']['hostname']}/api/auth/login", json={
    "username": config['unvr']['username'],
    "password": config['unvr']['password'],
    "rememberMe": False,
})

if login_r.status_code != 200:
    raise Exception(f"Received {login_r.status_code} on POST /api/auth/login: {login_r.json()}")

bootstrap_r = session.get(f"https://{config['unvr']['hostname']}/proxy/protect/api/bootstrap")

site_name = bootstrap_r.json()['nvr']['name']

cameras = {}
for camera in bootstrap_r.json()['cameras']:
    cameras[camera['id']] = camera['name']

for camera_id in config['cameras']:

    camera_name = cameras[camera_id]
    event_r = session.get(f"https://{config['unvr']['hostname']}/proxy/protect/api/events?cameras={camera_id}&end&limit=100&orderDirection=ASC&start&types=motion&types=ring&types=smartDetectZone")

    for event in event_r.json():
        if camera_id in LAST_TOKENS.keys() and LAST_TOKENS[camera_id] >= event['start']:
            continue

        thumbnail_url = f"https://{config['unvr']['hostname']}/proxy/protect/api/events/{event['id']}/thumbnail?h=1080&w=1920"

        with session.get(thumbnail_url, stream=True, verify=False) as thumbnail_r:
            filename = os.path.join("thumbnails", f"{event['id']}.jpg")
            dt = datetime.utcfromtimestamp(event['start']/1000).replace(tzinfo=pytz.utc).astimezone(TIMEZONE)

            with open(filename, 'wb') as of:
                shutil.copyfileobj(thumbnail_r.raw, of)

        with open(filename, 'rb') as of:
            img_b64 = base64.b64encode(of.read()).decode('utf-8')

        msg = {
            "type":"message",
            "attachments":[
                {
                    "contentType":"application/vnd.microsoft.card.adaptive",
                    "contentUrl":None,
                    "content":{
                        "$schema":"http://adaptivecards.io/schemas/adaptive-card.json",
                        "type":"AdaptiveCard",
                        "version":"1.2",
                        "body":[
                            {
                                "type": "TextBlock",
                                "text": f"Motion Event at {site_name} {camera_name}",
                                "size": "Large",
                                "wrap": True,
                            },
                            {
                                "type": "TextBlock",
                                "text": dt.strftime("%a %H:%M:%S"),
                                "size": "Medium",
                                "weight": "Lighter",
                                "wrap": True,
                            },
                            {
                                "type": "Image",
                                "url": f"data:image/jpeg;base64,{img_b64}",
                            },
                        ]
                    }
                }
            ]
        }

        for webhook_url in config['webhooks']:
            webhook_r = session.post(webhook_url, json=msg)
            if webhook_r.status_code not in [200, 201]:
                raise Exception(f"Failed to POST to webhook {webhook_url} {webhook_r.status_code}: {webhook_r.json()}")

        LAST_TOKENS[camera_id] = event['start']
        with open(LAST_FILENAME, 'w') as of:
            json.dump(LAST_TOKENS, of)
