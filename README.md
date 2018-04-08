# Create proxy servers easy way
---

### How to use
- Install `ansible`
- go to digitalocean and create servers
- put their ips in `inventories/default`
- put your computer's ip in `group_vars/default.ml`
- run `ansible-playbook main.yml -i inventories/default`


### [Video tutorial](https://youtu.be/HAnamHPHEKc)
