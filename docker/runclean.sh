#!/bin/bash
sudo rm -rf /s100/galaxy_storage/*
sudo cp tfwelcome.html /s100/galaxy_storage/welcome.html
docker build -t toolfactory .
./startgaldock.sh

