# Auto boot

Starts the basestation automatically on the Raspberry Pi.

Two options:

- **systemd service** (headless): copy `auto_boot.service` to
  `/etc/systemd/system/`, then `sudo systemctl enable --now auto_boot`.
  Edit the paths in the service file if the repo is not at
  `/home/rover/rovers-basestation2`.
- **Desktop entry** (with GUI): copy `basestation.desktop` to
  `~/.config/autostart/`.

`auto_boot.py` is an optional pre-check that waits for the rover's XBee to
answer a ping before launching; use it as the ExecStart command instead of
`auto_boot.sh` if you want that behavior.
