#!/bin/sh

abort() {
    echo $@
    exit 1
}

VENV=/src/.venv_docker

[ ! -d /src ] && abort "You forgot to mount /src"

set -e

if [ ! -x $VENV/bin/portable-python ]; then
    set -x
    /usr/bin/python3 -mvenv $VENV
    $VENV/bin/python -mpip install -r /src/requirements.txt
    $VENV/bin/python -mpip install -e /src
fi

exec $VENV/bin/portable-python "$@"
