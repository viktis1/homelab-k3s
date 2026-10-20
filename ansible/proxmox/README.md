This code aims to create a reproducible workflow for Ansible. Since I have TOTP access for both the Proxmox Web access and SSH connections, the Ansible code requires your computer to create an SSH connection tat Ansible can use.
```bash
ssh -M -S ~/.ssh/pve-ansible.sock \
  -o ControlPersist=10m \
  ___userWithSUDO___@192.168.1.152
```
Ansible is then configured to use this master connection to connect and run the commands. 
```bash
ansible-playbook  \
    -i ansible/proxmox/inventory.ini \
    ansible/proxmox/00-create-zfs-pool-DESTRUCTIVE.yaml \
    --ask-become-pass
```
```bash
ansible-playbook  \
    -i ansible/proxmox/inventory.ini \
    ansible/proxmox/01-configure-storage.yaml \
    --ask-become-pass
```
```bash
ansible-playbook  \
    -i ansible/proxmox/inventory.ini \
    ansible/proxmox/02-install-pbs-on-host.yaml \
    --ask-become-pass \
    -e @ansible/proxmox/pbs-secret.yaml
```

# Conclusion
After running all the code above, you should now have a ZFS backup storage and a PBS server. So now you can make vmdumpz that uses incremental loading via PBS. It was not needed to turn the backup storage into ZFS, since backups are created using PBS. However, the storage was turned into ZFS in order to have matching storage systems, which could be interesting if I want to use it for ZFS mirroring later. To manually create backups with PBS, run the following commands after turning the VMs off.
```bash
sudo vzdump 211 212 213 214 \
  --storage pbs-local \
  --mode snapshot
  ```