#!/bin/sh
set -e

if [ "${CROND_ENABLED}" = true ]; then
    supercronic /app/crontab &
    status=$?
    if [ $status -ne 0 ]; then
         echo "Failed to start supercronic: $status"
         exit $status
    fi
fi
exec "$@"
