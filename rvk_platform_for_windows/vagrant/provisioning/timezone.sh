#!/usr/bin/env bash

echo "==============================================================="
echo "=================GETTING TIMEZONE RIGHT========================"
echo "==============================================================="

sudo rm /etc/localtime
sudo ln -s /usr/share/zoneinfo/Europe/Berlin /etc/localtime
