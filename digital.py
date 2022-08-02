import time
import yaml
import json
import random
import string
import urllib.request
from typing import List
from optparse import OptionParser


import digitalocean
import ansible_runner

import config


class Droplet:
    def __init__(self, droplet):
        self.droplet = droplet
        self.status = None
        self.ip_address = None

    @property
    def urn(self):
        return f"do:droplet:{self.droplet.id}"

    @property
    def is_ready(self):
        if not self.ip_address:
            self.droplet.load()
            self.ip_address = self.droplet.ip_address
        return self.ip_address is not None


class DoAPI:
    """Class for working with DigitalOcean's API"""

    def __init__(self, token):
        self.token = token
        self.manager = digitalocean.Manager(token=token)
        self.ssh_keys = self.manager.get_all_sshkeys()
        self.droplets: List[Droplet] = []
        self.ip_addresses: List[str] = []
        self.tag = config.DROPLET_TAG

    def create_droplet(self, region: str):
        name = "Temp-" + "".join(random.choices(string.digits, k=10))
        droplet = digitalocean.Droplet(
            token=self.token,
            name=name,
            region=region,
            image=config.DROPLET_IMAGE,
            size_slug=config.DROPLET_SIZE_SLUG,
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
        for _ in range(quantity):
            self.create_droplet(region=config.REGION)

        # waiting for droplets to have an IPs
        while not all(droplet.is_ready for droplet in self.droplets):
            time.sleep(1)

        # gathering IPs
        for droplet in self.droplets:
            self.ip_addresses.append(droplet.ip_address)


class AnsibleWriter:
    """Class for manipulating ansible group vars and inventories"""

    def __init__(self, digital_ocean: DoAPI):
        self.digital_ocean = digital_ocean

    def _update_group_vars(self):
        with urllib.request.urlopen("https://api.ipify.org/?format=json") as url:
            mashine_ip = json.loads(url.read().decode())["ip"]
        with open("group_vars/default.yml", "w") as file:
            yaml.dump({"whitelisted_ip": mashine_ip}, file, default_flow_style=False)

    def _update_inventories(self):
        result_string = "[default]\n"
        for server_ip in self.digital_ocean.ip_addresses:
            server_string = f"{server_ip} ansible_user=root\n"
            result_string += server_string
        with open("inventories/default", "w") as file:
            file.write(result_string)
            file.close()

    def refresh_variables(self):
        self._update_group_vars()
        self._update_inventories()


if __name__ == "__main__":
    parser = OptionParser()
    parser.add_option("--create", dest="create_arg", type="int", help="Creates Droplets")
    parser.add_option("--destroy", dest="destroy_arg", type="string", help="Creates Droplets", default=False)

    (options, args) = parser.parse_args()
    digital_ocean = DoAPI(token=config.DIGITAL_OCEAN_API_TOKEN)
    writer = AnsibleWriter(digital_ocean=digital_ocean)

    if options.create_arg:
        print(f"Creating {options.create_arg} droplets, please wait....")
        digital_ocean.create_batch(options.create_arg)
        print("Updating Ansible config files...")
        writer.refresh_variables()
        ansible_runner.run(private_data_dir=".", inventory="inventories/default", playbook="playbook.yml")

    elif options.destroy_arg == "True":
        print("Destroying All Droplets...")
        digital_ocean.destroy_batch()
        print("Destroyed. Exiting")
