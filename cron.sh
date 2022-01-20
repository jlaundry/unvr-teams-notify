#!/bin/bash

cd /opt/unvr-teams-notify
source .env/bin/activate

if [ -f "/tmp/unvr-teams-notify.lock" ]; then
    echo "Lockfile exists, bailing out"
else
    touch /tmp/unvr-teams-notify.lock
    python /opt/unvr-teams-notify/unvr-teams-notify.py
    rm /tmp/unvr-teams-notify.lock
fi