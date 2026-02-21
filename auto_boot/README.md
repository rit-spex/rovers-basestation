# SPEX Rover Basestation auto boot

Autoboot service that allow the basestation to automatically boot on start up.

## Raspberry pi based
If the basestation is running on raspberry pi, then we will use the raspberry pi autoboot management which allow us to run GUI after the desktop is loaded

### 1. Make the autostart directory in raspberry autoboot config
```
mkdir ~/.config/autostart/
```

### 2. Copy the basestation.desktop file to raspberry autoboot config
```
cp ~/rovers-basestation/auto_boot/basestation.desktop ~/.config/autostart/
```

### 3. Change the file permission to allow it to be executable
```
chmod 777 ~/.config/autostart/basestation.desktop
chmod 777 ~/rovers-basestation/auto_boot/auto_boot.sh
```

### 4. Restart the raspberry and it should automatically open the GUI

## Other hardware running UNIX linux
If the basestation is not running on raspberry pi, but is running a UNIX based then we will use `systemctl` to handle autoboot

### 1. Copy the auto_boot.service file to systemd config path
```
cp ~/rovers-basestation/auto_boot/auto_boot.service /etc/systemd/system/
```

### 2. Reload the systemctl and enable the service
```
sudo systemctl daemon-reload
sudo systemctl enable auto_boot.service
```

### 3. Test that the file works (remember that this is a headless, so there is no GUI. Use the controller to test if it is running)
```
sudo systemctl start auto_boot.service
```

### 4. Reboot the system
```
sudo reboot
```

## Troubleshooting step
Use `systemctl` status to see the status of the service

### 1. Refresh the daemon to see the update status of the auto_boot.service
```
sudo systemctl daemon-reload
```

### 2. See the status of the auto_boot.service
```
sudo systemctl status auto_boot.service
```