# Running the tracker on an Azure VM

The tracker has to run around the clock for days. These steps put it on a small Azure
Linux VM (paid for by Azure for Students credit) that restarts it automatically, adds the
day's top channels every day, and keeps daily database backups.

What runs on the server:

| Unit | What it does |
|------|--------------|
| `twitchnet-tracker.service` | Runs `tracker.py` continuously; restarts it after crashes and reboots |
| `twitchnet-reseed.timer` | Daily at 20:00 UTC (01:30 IST): adds the top 300 live channels to the tracked list, backs up the database (keeps 7), restarts the tracker |

Sampling rule this gives: *every channel in the top 300 live at 20:00 UTC on any day of the run*.
Channels are added, never removed, so each keeps its full history.

## 1. Activate Azure for Students

1. Go to <https://azure.microsoft.com/free/students> and sign in with your college email.
2. Complete the student verification. No credit card is needed; you get credit to spend on Azure.

## 2. Create the VM

In the [Azure portal](https://portal.azure.com): **Virtual machines → Create → Azure virtual machine**.

| Setting | Value |
|---------|-------|
| Subscription | Azure for Students |
| Resource group | Create new: `twitchnet` |
| Virtual machine name | `twitchnet-tracker` |
| Region | Central India (or any region your subscription allows) |
| Image | Ubuntu Server 24.04 LTS - x64 Gen2 |
| Size | **Standard_B1ms** (1 vCPU, 2 GiB RAM). B1s (1 GiB) can run out of memory while installing |
| Authentication type | SSH public key |
| Username | `azureuser` |
| SSH public key source | Generate new key pair, name `twitchnet-tracker_key` |
| Public inbound ports | Allow selected ports: **SSH (22)** only |
| OS disk type (Disks tab) | Standard SSD |

**Review + create → Create**, then **Download private key and create resource**. Save the
`.pem` file somewhere safe (e.g. `C:\Users\<you>\.ssh\`). You can't download it again.

When deployment finishes, open the VM and copy its **Public IP address**.

## 3. Connect from Windows

In PowerShell (replace the path and IP):

```powershell
ssh -i C:\Users\<you>\.ssh\twitchnet-tracker_key.pem azureuser@<PUBLIC-IP>
```

Type `yes` the first time. If SSH says the key file permissions are too open, run this once and retry:

```powershell
icacls C:\Users\<you>\.ssh\twitchnet-tracker_key.pem /inheritance:r /grant:r "$($env:USERNAME):R"
```

## 4. Install the tracker (on the VM)

```bash
git clone https://github.com/isametron/twitchnet-analytics.git
cd twitchnet-analytics
nano .env
```

In nano, type your two credentials, then save with `Ctrl+O`, `Enter`, `Ctrl+X`:

```
TWITCH_CLIENT_ID=...
TWITCH_CLIENT_SECRET=...
```

Then run the installer (about 5 minutes):

```bash
bash deploy/setup_vm.sh
```

It installs everything, runs the tests, seeds the top 300 live channels and starts the services.

## 5. Check on it

```bash
journalctl -u twitchnet-tracker -f              # live log (Ctrl+C to stop watching; the tracker keeps running)
systemctl status twitchnet-tracker              # running? since when?
systemctl list-timers twitchnet-reseed.timer    # when the next daily re-seed runs
```

A status line appears every 5 minutes with snapshot, chat and raid counts.

## 6. Download the data

Daily backups land in `~/twitchnet-analytics/data/processed/backups/`. To take one right now (on the VM):

```bash
cd ~/twitchnet-analytics && .venv/bin/python scripts/backup_db.py
```

Copy backups to your laptop (in PowerShell on the laptop):

```powershell
scp -i C:\Users\<you>\.ssh\twitchnet-tracker_key.pem "azureuser@<PUBLIC-IP>:twitchnet-analytics/data/processed/backups/*.db" .
```

To analyse a backup, copy it over `data/processed/twitchnet.db` in your local repo (keep your own copy first).

## 7. Update the code

After pushing changes to GitHub (on the VM):

```bash
cd ~/twitchnet-analytics && git pull && sudo systemctl restart twitchnet-tracker
```

## 8. Costs and shutting down

- Standard_B1ms costs roughly $15-20 per month, well within the student credit for a few weeks.
  Check **Cost Management** in the portal now and then.
- When collection is finished: take a final backup, download it, then **Stop** the VM in the
  portal (it shows *Stopped (deallocated)* and compute billing stops), or delete the `twitchnet`
  resource group to remove everything.
