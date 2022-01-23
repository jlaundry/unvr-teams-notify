# unvr-teams-notify

A simple Python script and cron task to fetch motion events from UniFi Protect (UNVR), and push to Microsoft Teams Webhooks.

## Setup

You will need:

- 1 or more Teams channels with an Incoming Webhook configured
- A host with Python 3 and suitable user (i.e., replacing `botuser` in the install script below)
- A UNVR user with View permissions on the cameras you need to monitor

```bash

cd /opt
git clone https://github.com/jlaundry/unvr-teams-notify.git
cd unvr-teams-notify
python3 -m venv .env
source .env/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cat << EOF > /opt/unvr-teams-notify/config.json
{
    "webhooks": [
        "https://contoso.webhook.office.com/webhookb2/9085988e-32dc-4fbb-96ce-bf5c0f5a8551@e44937c5-a32e-422e-8ac9-07a90c7c7e5b/IncomingWebhook/9833fac87f5a518478ba16713db44c5e/c696c152-5bcb-49ec-ad5c-b33215aa9d47"
    ],
    "unvr": {
        "hostname": "192.168.1.66",
        "username": "bot",
        "password": "Password123",
        "verify_tls": false
    },
    "cameras": [
        "407b264fb4c64e8234bc7c50",
        "3b9ceaecb658e8f6c3cfc581"
    ],
    "timezone": "Pacific/Auckland"
}
EOF

touch /var/log/unvr-teams-notify.log
chown botuser:botuser /var/log/unvr-teams-notify.log

echo '* * * * * botuser /opt/unvr-teams-notify/cron.sh >> /var/log/unvr-teams-notify.log 2>&1' > /etc/cron.d/unvr-teams-notify

```
