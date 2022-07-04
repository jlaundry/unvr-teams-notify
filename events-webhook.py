from datetime import datetime, timedelta
import base64
import json
import os
import pytz
import requests
import shutil
import tzlocal

from azure.storage.blob import BlobServiceClient, ContentSettings, generate_blob_sas

session = requests.Session()

with open('config.json', 'r') as of:
    config = json.load(of)

if 'timezone' in config.keys():
    TIMEZONE = pytz.timezone(config['timezone'])
else:
    TIMEZONE = tzlocal.get_localzone()


def upload_thumbnail(filename, data):
    blob_service_client = BlobServiceClient.from_connection_string(config['storage']['connection_string'])
    blob_client = blob_service_client.get_blob_client(container=config['storage']['container_name'], blob=filename)
    blob_client.upload_blob(
        data,
        overwrite=True,
        content_settings=ContentSettings(content_type='image/gif'),
    )

    sas_token = generate_blob_sas(
        config['storage']['account_name'],
        blob_client.container_name,
        blob_client.blob_name,
        account_key=config['storage']['account_key'],
        expiry = datetime.now() + timedelta(days=14),
        permission="r",
    )

    return blob_client.url + '?' + sas_token

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

    start = "start"
    if camera_id in LAST_TOKENS:
       start += f"={LAST_TOKENS[camera_id]}"

    camera_name = cameras[camera_id]
    event_r = session.get(f"https://{config['unvr']['hostname']}/proxy/protect/api/events?cameras={camera_id}&end&limit=100&orderDirection=ASC&{start}&types=motion&types=ring&types=smartDetectZone")

    for event in event_r.json():
        if camera_id in LAST_TOKENS.keys() and LAST_TOKENS[camera_id] >= event['start']:
            continue

        LAST_TOKENS[camera_id] = event['start']
        dt = datetime.utcfromtimestamp(event['start']/1000).replace(tzinfo=pytz.utc).astimezone(TIMEZONE)

        print(f"Event at {event['start']} weekday:{dt.weekday()} hour:{dt.hour}")

        # TODO: configise
        print(f"Event at: {dt}")
        if dt.weekday() in range(5,7):
            pass
        else:
            if dt.hour in range(8,18):
                print("Skipping")
                continue

        thumbnail_url = f"https://{config['unvr']['hostname']}/proxy/protect/api/events/{event['id']}/thumbnail?h=350&w=350"
        gif_url = f"https://{config['unvr']['hostname']}/proxy/protect/api/events/{event['id']}/animated-thumbnail?h=480&keyFrameOnly=true&speedup=10&w=832"

        with session.get(thumbnail_url, stream=True, verify=False) as thumbnail_r:
            filename = os.path.join("thumbnails", f"{event['id']}.jpg")
            with open(filename, 'wb') as of:
                shutil.copyfileobj(thumbnail_r.raw, of)

        with open(filename, 'rb') as of:
            img_b64 = base64.b64encode(of.read()).decode('utf-8')

        with session.get(gif_url, stream=True, verify=False) as gif_r:
            gif_url = upload_thumbnail(f"{event['id']}.gif", gif_r)
            print(gif_url)

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
                                "text": dt.strftime("%a, %-d %b %H:%M:%S"),
                                "size": "Medium",
                                "weight": "Lighter",
                                "wrap": True,
                            },
                            {
                                "type": "Image",
                                "url": f"data:image/gif;base64,{img_b64}",
                            },
                            {
                                "type": "TextBlock",
                                "text": f"[View GIF]({gif_url})",
                            },
                        ]
                    }
                }
            ]
        }

        print(f"POSTing message")

        for webhook_url in config['webhooks']:
            webhook_r = session.post(webhook_url, json=msg)
            # print(f"{webhook_url}: {json.dumps(msg)}")
            if webhook_r.status_code not in [200, 201]:
                raise Exception(f"Failed to POST to webhook {webhook_url} {webhook_r.status_code}: {webhook_r.json()}")
            # print(webhook_r.json())

with open(LAST_FILENAME, 'w') as of:
    json.dump(LAST_TOKENS, of)

