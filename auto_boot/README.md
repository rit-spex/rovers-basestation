# Auto boot

Starts the basestation automatically on the Raspberry Pi.

Two options:

- **systemd service** (headless): copy `auto_boot.service` to
  `/etc/systemd/system/`, then `sudo systemctl enable --now auto_boot`.
  Edit the paths in the service file if the repo is not at
  `/home/rover/rovers-basestation`.
- **Desktop entry** (with GUI): copy `basestation.desktop` to
  `~/.config/autostart/`.

`auto_boot.sh` and `basestation.desktop` must keep their executable bit
(`chmod +x auto_boot/auto_boot.sh auto_boot/basestation.desktop`); the
desktop entry launches the script directly and otherwise fails with
"Permission denied".

`auto_boot.py` is an optional pre-check that waits for the rover's XBee to
answer a ping before launching. To use it, point the service at the venv
interpreter instead of `auto_boot.sh`:

```ini
ExecStart=/home/rover/rovers-basestation/.venv/bin/python /home/rover/rovers-basestation/auto_boot/auto_boot.py
```
