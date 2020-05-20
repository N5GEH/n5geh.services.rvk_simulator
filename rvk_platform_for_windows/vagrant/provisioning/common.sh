#!/usr/bin/env bash

echo "==============================================================="
echo "====================UPGRADE SYSTEM============================="
echo "==============================================================="

sudo apt-get install gcc make -y
sudo apt-get install mc -y
sudo apt-get upgrade -y
sudo apt-get install dos2unix -y

echo -e "\nsource venv/bin/activate" >> /home/vagrant/.bashrc
echo -e "\ncd /vagrant" >> .bashrc
sudo chown -R vagrant:vagrant /home/vagrant/venv

sudo apt-get install mosquitto-clients -y

# Aliases for Vagrant
echo -e "\nsource /vagrant/vagrant/provisioning/vagrant-aliases" >> /home/vagrant/.bashrc

echo -e "\nsudo sysctl -w vm.max_map_count=262144" >> /home/vagrant/.bashrc

echo -e "\nchmod +x service provision-devices subscription-orion" >> /home/vagrant/.bashrc

#echo -e "\n./service start" >> /home/vagrant/.bashrc
