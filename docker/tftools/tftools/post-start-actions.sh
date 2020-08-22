#!/usr/bin/env bash
# hook to install tf demo workflow
echo "#### post start actions.sh hook happening"
sudo chown -R $GALAXY_USER:$GALAXY_USER /tftools
#python3 -m venv /tftools/.venv
source /galaxy_venv/bin/activate && /galaxy_venv/bin/python3 -m pip install -r /tftools/requirements.txt  && /galaxy_venv/bin/python3 /tftools/postinstall.py








