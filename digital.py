import os
import time
import random
import string
import ruamel.yaml
import digitalocean
import urllib.request
from optparse import OptionParser
from ruamel.yaml.util import load_yaml_guess_indent


class Writer:
    def __init__(self):
        self.mashine_ip = None
        self.group_vars_file = 'group_vars/default.yml'

    def _update_current_ip(self):
        self.mashine_ip = urllib.request.urlopen('https://ident.me').read().decode('utf8')
        with open(self.group_vars_file) as file:
            config, ind, bsi = load_yaml_guess_indent(file)
        config['whitelisted_ip'] = self.mashine_ip
        with open(self.group_vars_file, 'w') as file:
            ruamel.yaml.round_trip_dump(
                config, file,
                indent=ind, block_seq_indent=bsi,
            )

    def _update_servers_ips(self):
        result_string = '[default]\n'
        for server_ip in bot.ip_addresses:
            server_string = f'{server_ip} ansible_user=root\n'
            result_string += server_string
        with open('inventories/default', 'w') as file:
            file.write(result_string)
            file.close()

    def refresh(self):
        self._update_current_ip()
        self._update_servers_ips()


class Droplet:
    def __init__(self, droplet):
        self.droplet = droplet
        self.status = None
        self.ip_address = None

    @property
    def is_ready(self):
        if not self.ip_address:
            self.droplet.load()
            self.ip_address = self.droplet.ip_address
        return self.ip_address is not None


class DigitalBot:
    def __init__(self, token):
        self.token = token
        self.manager = digitalocean.Manager(token=token)
        self.ssh_keys = self.manager.get_all_sshkeys()
        self.droplets = []
        self.tag = 'temp'
        self.ip_addresses = []

    def create_droplet(self):
        name = 'Temp-' + ''.join(random.choices(string.digits, k=10))
        droplet = digitalocean.Droplet(
            token=self.token,
            name=name,
            region='sfo2',
            image='ubuntu-20-04-x64',
            size_slug='s-1vcpu-1gb',      # 1GB RAM, 1 vCPU
            ssh_keys=self.ssh_keys,
            backups=False,
            tags=[self.tag],
        )
        droplet.create()
        self.droplets.append(Droplet(droplet))

    def destroy_batch(self):
        test_droplets = self.manager.get_all_droplets(tag_name=self.tag)
        for droplet in test_droplets:
            droplet.destroy()

    def create_batch(self, quantity):
        counter = 0
        while counter < quantity:
            self.create_droplet()
            counter += 1
        # waiting for droplets to load
        while not all(droplet.is_ready for droplet in self.droplets):
            time.sleep(1)
        # printing IPs
        for droplet in self.droplets:
            self.ip_addresses.append(droplet.ip_address)


if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('--create', dest='create_arg', type='int',
                      help='Creates Droplets')
    parser.add_option('--destroy', dest='destroy_arg', type='string',
                      help='Creates Droplets', default=False)

    (options, args) = parser.parse_args()
    writer = Writer()
    bot = DigitalBot(token='token_goes_here')

    if options.create_arg:
        print(f'Creating {options.create_arg} droplets, please wait....')
        bot.create_batch(options.create_arg)
        print('Done')
        print('Updating Ansible config files...')
        writer.refresh()
        print('Waiting 60s for servers to boot...')
        time.sleep(60)
        os.system('ansible-playbook main.yml -i inventories/default')

    elif options.destroy_arg == 'True':
        print('Destroying All Droplets...')
        bot.destroy_batch()
        print('Destroyed. Exiting')
