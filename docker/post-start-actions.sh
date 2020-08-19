#!/usr/bin/env bash
# hook to install tf demo workflow
echo "#### post start actions.sh hook happening"
sudo chown -R $GALAXY_USER:$GALAXY_USER /tftools
/galaxy_venv/bin/python3 -m pip install --upgrade pip
/galaxy_venv/bin/python3 -m pip  install --upgrade planemo galaxyxml ephemeris bioblend
/galaxy_venv/bin/python3 /tftools/postinstall.py





