#!/bin/sh
set -eu

python /srv/app/scripts/bootstrap_container.py

exec "$@"
