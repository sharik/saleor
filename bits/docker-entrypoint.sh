#!/bin/sh
set -e

if [ ${CROND_ENABLED} = true ]; then
    crontab /app/crontab
    crond -b
fi
exec "$@"
