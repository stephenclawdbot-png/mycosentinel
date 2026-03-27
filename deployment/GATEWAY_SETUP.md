# MycoSentinel Gateway Setup Guide
## Raspberry Pi 4B - Production Deployment

**Document Version:** 1.0  
**Target Hardware:** Raspberry Pi 4B (4GB RAM minimum)  
**Gateway IP:** 192.168.1.100  
**Mesh SSID:** mycosentinel-mesh  

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [OS Installation](#1-os-installation)
3. [MQTT Broker Configuration](#2-mqtt-broker-configuration)
4. [Network Setup - Static IP](#3-network-setup---static-ip)
5. [WiFi AP Configuration](#4-wifi-ap-configuration-for-mesh-backbone)
6. [Security Hardening](#5-security-hardening)
7. [Monitoring & Maintenance](#6-monitoring--maintenance)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Hardware
- Raspberry Pi 4B (4GB+ RAM recommended)
- MicroSD card (32GB+ Class 10)
- Power supply (5V/3A USB-C)
- Ethernet cable (for initial setup)
- Optional: Pi-compatible WiFi dongle (onboard WiFi supported)

### Required Software (on workstation)
- Raspberry Pi Imager
- SSH client (OpenSSH/PuTTY)
- `nmap` or `arp-scan` (for network discovery)

---

## 1. OS Installation

### 1.1 Download Raspberry Pi Imager

```bash
# macOS
brew install --cask raspberry-pi-imager

# Ubuntu/Debian
sudo apt update && sudo apt install rpi-imager

# Windows: Download from https://www.raspberrypi.com/software/
```

### 1.2 Flash OS to MicroSD

1. **Insert MicroSD card** into workstation
2. **Launch Raspberry Pi Imager**
3. **Select Device:** Raspberry Pi 4
4. **Select OS:** Raspberry Pi OS (64-bit) Lite (no desktop)
5. **Configure Options (⚙️ icon):**
   - **Hostname:** `mycosentinel-gw`
   - **Enable SSH:** Password authentication
   - **Username:** `mycosentinel`
   - **Password:** [Generate strong password]
   - **WiFi:** Skip for now (we'll configure AP mode)
   - **Locale:** Set timezone and keyboard

6. **Write** to SD card

### 1.3 First Boot

```bash
# Insert SD card into Pi, connect Ethernet
# Power on - wait 60 seconds for boot

# Find Pi on network (from workstation)
sudo arp-scan --localnet | grep -i raspberry
# OR
nmap -sn 192.168.1.0/24 | grep -i raspberry

# Default hostname fallback
ping mycosentinel-gw.local
```

### 1.4 Initial SSH Access

```bash
ssh mycosentinel@192.168.1.XXX  # Use discovered IP

# Update system immediately
sudo apt update && sudo apt full-upgrade -y
sudo reboot
```

---

## 2. MQTT Broker Configuration

### 2.1 Install Mosquitto

```bash
# Update and install Mosquitto with clients
sudo apt update
sudo apt install -y mosquitto mosquitto-clients

# Enable service auto-start
sudo systemctl enable mosquitto

# Verify installation
mosquitto -h
systemctl status mosquitto
```

### 2.2 Create Mosquitto Configuration

```bash
# Backup default config
sudo cp /etc/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf.backup

# Create custom configuration
sudo tee /etc/mosquitto/mosquitto.conf << 'EOF'
# MycoSentinel MQTT Gateway Configuration

# Basic settings
pid_file /run/mosquitto/mosquitto.pid
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log

# Network listener - bind to all interfaces
listener 1883 0.0.0.0

# Allow anonymous for internal mesh (harden in production)
allow_anonymous true

# Message size limits for sensor data
max_packet_size 65536
message_size_limit 65536

# Persistence settings
autosave_interval 1800
autosave_on_changes false
persistence_file mosquitto.db

# Logging
log_type error
log_type warning
log_type information
log_type subscribe
log_type unsubscribe

# Connection limits for 10-node mesh
max_connections 50
max_inflight_messages 100
max_queued_messages 1000

# Include additional configs
include_dir /etc/mosquitto/conf.d
EOF
```

### 2.3 Create Data Directory Structure

```bash
# Create directories for sensor data persistence
sudo mkdir -p /var/lib/mycosentinel/data
sudo mkdir -p /var/lib/mycosentinel/logs
sudo chown -R mosquitto:mosquitto /var/lib/mycosentinel

# Create log directory
sudo mkdir -p /var/log/mycosentinel
sudo chown mosquitto:mosquitto /var/log/mycosentinel
```

### 2.4 Firewall Rules for MQTT

```bash
# Install and configure UFW
sudo apt install -y ufw

# Default deny incoming
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow 22/tcp

# Allow MQTT
sudo ufw allow 1883/tcp
sudo ufw allow 1883/udp

# Allow WebSocket MQTT (optional)
sudo ufw allow 9001/tcp

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status verbose
```

### 2.5 Test MQTT Broker

```bash
# Restart mosquitto
sudo systemctl restart mosquitto
sudo systemctl status mosquitto

# Test local publish/subscribe
# Terminal 1 (subscriber):
mosquitto_sub -h localhost -t "mycosentinel/test" -v

# Terminal 2 (publisher):
mosquitto_pub -h localhost -t "mycosentinel/test" -m "Gateway online"

# Check logs
sudo tail -f /var/log/mosquitto/mosquitto.log
```

---

## 3. Network Setup - Static IP

### 3.1 Configure Netplan (Modern Ubuntu/Debian)

```bash
# Check current network config
ip addr show

# Create static IP configuration
sudo tee /etc/dhcpcd.conf << 'EOF'
# MycoSentinel Gateway Static IP Configuration

# Ethernet interface
interface eth0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8

# WiFi interface (AP mode - configured separately)
interface wlan0
nohook wpa_supplicant
EOF

# Alternative: Using network interfaces file
sudo tee /etc/network/interfaces.d/static << 'EOF'
auto eth0
iface eth0 inet static
    address 192.168.1.100
    netmask 255.255.255.0
    gateway 192.168.1.1
    dns-nameservers 192.168.1.1 8.8.8.8

auto wlan0
iface wlan0 inet static
    address 10.0.0.1
    netmask 255.255.255.0
EOF
```

### 3.2 Configure systemd-networkd (Alternative)

```bash
# Create network configuration
sudo tee /etc/systemd/network/10-eth0.network << 'EOF'
[Match]
Name=eth0

[Network]
Address=192.168.1.100/24
Gateway=192.168.1.1
DNS=192.168.1.1
DNS=8.8.8.8
EOF

sudo tee /etc/systemd/network/20-wlan0.network << 'EOF'
[Match]
Name=wlan0

[Network]
Address=10.0.0.1/24
DHCPServer=yes

[DHCPServer]
PoolOffset=100
PoolSize=50
EmitDNS=yes
DNS=10.0.0.1
EOF

# Enable systemd-networkd
sudo systemctl enable systemd-networkd
sudo systemctl start systemd-networkd
```

### 3.3 Set Hostname

```bash
# Set hostname
sudo hostnamectl set-hostname mycosentinel-gw

# Update /etc/hosts
echo "192.168.1.100 mycosentinel-gw" | sudo tee -a /etc/hosts

# Verify
hostnamectl status
```

### 3.4 Network Verification

```bash
# After reboot, verify static IP
ip addr show eth0
ip route show

# Test connectivity
ping 8.8.8.8 -c 4
ping mycosentinel-gw.local -c 4

# DNS resolution
dig google.com
```

---

## 4. WiFi AP Configuration for Mesh Backbone

### 4.1 Install Required Packages

```bash
# Install hostapd and dnsmasq
sudo apt update
sudo apt install -y hostapd dnsmasq

# Stop services initially
sudo systemctl stop hostapd
sudo systemctl stop dnsmasq
```

### 4.2 Configure hostapd (Access Point)

```bash
# Create hostapd configuration
sudo tee /etc/hostapd/hostapd.conf << 'EOF'
# MycoSentinel Mesh Access Point Configuration
interface=wlan0
driver=nl80211

# Network Name
ssid=mycosentinel-mesh

# Channel and mode
channel=7
hw_mode=g
ieee80211n=1
wmm_enabled=1

# Security (WPA2)
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP

# Generate strong password and set here
# Pre-generated for initial setup: MycoMesh2024!
wpa_passphrase=MycoMesh2024!

# Beacon interval (ms)
beacon_int=100

# Various optimizations
dtim_period=2
max_num_sta=15
rts_threshold=-1
fragm_threshold=-1
EOF

# Set configuration path
sudo tee /etc/default/hostapd << 'EOF'
RUN_DAEMON=yes
DAEMON_CONF="/etc/hostapd/hostapd.conf"
EOF
```

### 4.3 Configure dnsmasq (DHCP Server)

```bash
# Backup original
sudo mv /etc/dnsmasq.conf /etc/dnsmasq.conf.backup

# Create new configuration
sudo tee /etc/dnsmasq.conf << 'EOF'
# MycoSentinel Mesh DHCP Configuration

# Interface to listen on
interface=wlan0
bind-interfaces

# DHCP range for mesh nodes
# Reserves 10.0.0.100-149 for sensor nodes
dhcp-range=10.0.0.100,10.0.0.149,255.255.255.0,24h

# Gateway and DNS
dhcp-option=3,10.0.0.1
dhcp-option=6,10.0.0.1,8.8.8.8

# Domain
domain=mycosentinel.mesh
local=/mycosentinel.mesh/

# Static leases (reserve IPs for known nodes)
# Format: dhcp-host=MAC,IP,hostname
# dhcp-host=aa:bb:cc:dd:ee:01,10.0.0.101,node-01
# dhcp-host=aa:bb:cc:dd:ee:02,10.0.0.102,node-02

# Logging
log-facility=/var/log/dnsmasq.log
log-dhcp

# Cache settings
cache-size=1000
EOF
```

### 4.4 Configure Network Bridge (Optional but Recommended)

```bash
# Install bridge utilities
sudo apt install -y bridge-utils

# Configure bridge in /etc/dhcpcd.conf
sudo tee -a /etc/dhcpcd.conf << 'EOF'
# Bridge configuration
denyinterfaces wlan0

interface br0
    static ip_address=192.168.1.100/24
    static routers=192.168.1.1
    static domain_name_servers=192.168.1.1
EOF

# Alternative: Use routing instead of bridging
# This allows mesh subnet to route to main network
```

### 4.5 IP Forwarding and Routing

```bash
# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Make persistent
sudo tee -a /etc/sysctl.conf << 'EOF'
# Enable IP forwarding for mesh gateway
net.ipv4.ip_forward=1
EOF

# Configure iptables rules
sudo iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
sudo iptables -A FORWARD -i eth0 -o wlan0 -m state --state RELATED,ESTABLISHED -j ACCEPT
sudo iptables -A FORWARD -i wlan0 -o eth0 -j ACCEPT

# Save iptables rules
sudo apt install -y iptables-persistent
sudo netfilter-persistent save
```

### 4.6 Start Services

```bash
# Unblock WiFi (may be blocked by RF-kill)
sudo rfkill unblock wifi

# Enable and start services
sudo systemctl unmask hostapd
sudo systemctl enable hostapd
sudo systemctl start hostapd

sudo systemctl enable dnsmasq
sudo systemctl start dnsmasq

# Verify services
sudo systemctl status hostapd
sudo systemctl status dnsmasq
```

### 4.7 Mesh Network Verification

```bash
# Check WiFi interface
ip addr show wlan0
iwconfig wlan0

# Check connected clients
# From another device, connect to "mycosentinel-mesh"

# View DHCP leases
sudo cat /var/lib/dhcp/dhcpd.leases
# OR
cat /var/lib/misc/dnsmasq.leases

# Verify AP is broadcasting
sudo iw dev wlan0 scan | grep SSID
```

---

## 5. Security Hardening

### 5.1 Change Default Passwords

```bash
# Change system password
sudo passwd mycosentinel

# Change WiFi password
sudo nano /etc/hostapd/hostapd.conf
# Edit: wpa_passphrase=YOUR_NEW_STRONG_PASSWORD

# Restart WiFi
sudo systemctl restart hostapd
```

### 5.2 Secure SSH

```bash
# Edit SSH configuration
sudo nano /etc/ssh/sshd_config

# Recommended changes:
# Port 2222                      # Change from default 22
# PermitRootLogin no
# PasswordAuthentication no      # Use keys only
# PubkeyAuthentication yes
# MaxAuthTries 3
# ClientAliveInterval 300
# ClientAliveCountMax 2

# Restart SSH
sudo systemctl restart sshd
```

### 5.3 Install and Configure Fail2ban

```bash
sudo apt install -y fail2ban

# Create local configuration
sudo tee /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 5.4 Setup Automatic Updates

```bash
# Install unattended-upgrades
sudo apt install -y unattended-upgrades

# Configure
sudo dpkg-reconfigure -plow unattended-upgrades

# Edit configuration
sudo nano /etc/apt/apt.conf.d/50unattended-upgrades

# Add security updates only
```

---

## 6. Monitoring & Maintenance

### 6.1 System Monitoring Script

```bash
# Create monitoring script
sudo tee /usr/local/bin/mycosentinel-monitor.sh << 'EOF'
#!/bin/bash
# MycoSentinel Gateway Monitor

LOG_FILE="/var/log/mycosentinel/gateway-monitor.log"
ALERT_FILE="/var/log/mycosentinel/alerts.log"

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" | tee -a "$LOG_FILE"
}

# Check system resources
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
mem_usage=$(free | grep Mem | awk '{printf "%.2f", $3/$2 * 100.0}')
disk_usage=$(df -h / | tail -1 | awk '{print $5}' | sed 's/%//')

log_message "CPU: ${cpu_usage}%, Memory: ${mem_usage}%, Disk: ${disk_usage}%"

# Check services
for service in mosquitto hostapd dnsmasq; do
    if systemctl is-active --quiet "$service"; then
        log_message "OK: $service is running"
    else
        log_message "ALERT: $service is NOT running"
        echo "$(date '+%Y-%m-%d %H:%M:%S') $service down" >> "$ALERT_FILE"
    fi
done

# Check MQTT broker
if timeout 5 mosquitto_pub -h localhost -t "mycosentinel/health" -m "$(date +%s)" 2>/dev/null; then
    log_message "OK: MQTT broker responsive"
else
    log_message "ALERT: MQTT broker not responding"
    echo "$(date '+%Y-%m-%d %H:%M:%S') MQTT unresponsive" >> "$ALERT_FILE"
fi

# Check network
if ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    log_message "OK: Internet connectivity"
else
    log_message "WARN: No internet connectivity"
fi
EOF

sudo chmod +x /usr/local/bin/mycosentinel-monitor.sh
```

### 6.2 Create Cron Job

```bash
# Add to crontab
sudo tee -a /etc/crontab << 'EOF'
# MycoSentinel monitoring
every 5 minutes
*/5 * * * * root /usr/local/bin/mycosentinel-monitor.sh

# Weekly log rotation
0 2 * * 0 root logrotate -f /etc/logrotate.d/mycosentinel 2>/dev/null || true
EOF
```

### 6.3 Log Rotation

```bash
sudo tee /etc/logrotate.d/mycosentinel << 'EOF'
/var/log/mycosentinel/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
}
EOF
```

---

## Troubleshooting

### WiFi Access Point Issues

```bash
# Check hostapd logs
sudo journalctl -u hostapd -f

# Check WiFi interface status
sudo iw dev wlan0 info
sudo iwconfig wlan0

# Restart WiFi
sudo systemctl restart hostapd
sudo systemctl restart dnsmasq

# Check RF-kill status
rfkill list
```

### MQTT Connection Issues

```bash
# Check mosquitto status
sudo systemctl status mosquitto

# Check mosquitto logs
sudo tail -f /var/log/mosquitto/mosquitto.log

# Test with verbose output
mosquitto_sub -h localhost -t "#" -v

# Check firewall
sudo ufw status
sudo iptables -L -n | grep 1883
```

### Network Issues

```bash
# Check IP configuration
ip addr show
ip route show

# Check DNS resolution
cat /etc/resolv.conf
systemd-resolve --status

# Test connectivity
ping -c 4 192.168.1.1
ping -c 4 8.8.8.8
```

### Service Won't Start

```bash
# Check for errors
sudo journalctl -xe

# Check service-specific logs
sudo journalctl -u hostapd
sudo journalctl -u mosquitto
sudo journalctl -u dnsmasq

# Verify configuration files
sudo hostapd -d /etc/hostapd/hostapd.conf
sudo mosquitto -c /etc/mosquitto/mosquitto.conf -t
```

---

## Quick Reference

| Service | Status Command | Restart Command |
|---------|----------------|-----------------|
| Mosquitto | `systemctl status mosquitto` | `sudo systemctl restart mosquitto` |
| hostapd | `systemctl status hostapd` | `sudo systemctl restart hostapd` |
| dnsmasq | `systemctl status dnsmasq` | `sudo systemctl restart dnsmasq` |
| Networking | `ip addr` / `iwconfig` | `sudo systemctl restart networking` |

| Port | Service | Purpose |
|------|---------|---------|
| 22/2222 | SSH | Remote access |
| 1883 | MQTT | Sensor communication |
| 9001 | MQTT WebSocket | Web dashboard (optional) |

---

## Next Steps

1. **Flash SD cards** using this guide
2. **Boot first gateway** at 192.168.1.100
3. **Test mesh connectivity** with first sensor node
4. **Deploy remaining 9 nodes** following sensor node setup guide

---

**Document maintained by:** MycoSentinel Dev Team  
**Last updated:** 2026-03-28  
**Version:** 1.0
