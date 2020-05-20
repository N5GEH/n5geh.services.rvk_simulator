#!/usr/bin/env bash

echo "==============================================================="
echo "====================INSTALLING PYTHON=========================="
echo "==============================================================="

sudo apt-get -y update

sudo apt-get install -y libreadline-dev libsqlite3-dev libssl-dev

sudo apt-get install -y python3-pip

sudo pip3 install virtualenv

cd /home/vagrant
virtualenv --python=python3.6 venv
source venv/bin/activate
