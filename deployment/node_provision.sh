#!/bin/bash
# MycoSentinel Node Provisioning Script
# For Raspberry Pi Zero 2 W and Pi 4
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/yourrepo/mycosentinel/main/deployment/node_provision.sh | sudo bash
#   OR download and run: sudo bash node_provision.sh
#
# This script:
#   - Configures Raspberry Pi OS for headless sensor operation
#   - Installs all dependencies (Python, I2C, camera, MQTT)
#   - Sets up the MycoSentinel software
#   - Configures WiFi, MQTT, and auto-start
#   - Optimizes power consumption for solar operation

set -euo pipefail

# ==============================================================================
# Configuration - MODIFY THESE VARIABLES
# ==============================================================================

NODE_ID="${NODE_ID:-node01}"                    # Unique node identifier
GATEWAY_IP="${GATEWAY_IP:-192.168.1.100}"        # MQTT broker IP
WIFI_SSID="${WIFI_SSID:-MYCOSENTINEL_FIELD}"     # WiFi network name
WIFI_PASS="${WIFI_PASS:-change_me_now}"          # WiFi password
TIMEZONE="${TIMEZONE:-UTC}"                      # System timezone
MQTT_USER="${MQTT_USER:-$NODE_ID}"              # MQTT username
MQTT_PASS="${MQTT_PASS:-change_me_now}"           # MQTT password

# Git repository (optional - set to use latest code)
GIT_REPO="${GIT_REPO:-https://github.com/stephenclawdbot-png/mycosentinel.git}"
GIT_BRANCH="${GIT_BRANCH:-main}"

# ==============================================================================
# Colors for output
# ==============================================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ==============================================================================
# Check if running as root
# ==============================================================================

if [[ $EUID -ne 0 ]]; then
   error "This script must be run as root (use sudo)"
   exit 1
fi

info "Starting MycoSentinel node provisioning..."
info "Node ID: $NODE_ID"
info "Gateway: $GATEWAY_IP"

# ==============================================================================
# System Update and Base Packages
# ==============================================================================

info "Updating system packages..."
apt-get update
apt-get upgrade -y
apt-get install -y \
    git \
    vim \
    htop \
    curl \
    wget \
    i2c-tools \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    libgpiod-dev \
    libjpeg-dev \
    libatlas-base-dev \
    libffi-dev \
    libssl-dev \
    mosquitto-clients \
    fswebcam \
    libcamera-dev \
    libcamera-apps \
    wireless-tools \
    wpasupplicant \
    ntp

success "Base packages installed"

# ==============================================================================
# Hardware Configuration
# ==============================================================================

info "Configuring hardware interfaces..."

# Enable I2C, SPI, and Camera
raspi-config nonint do_i2c 0
raspi-config nonint do_spi 0
raspi-config nonint do_camera 0
raspi-config nonint do_ssh 0
raspi-config nonint do_hostname "$NODE_ID"

# Disable Bluetooth (not needed, saves power)
info "Disabling Bluetooth to save power..."
systemctl stop bluetooth
systemctl disable bluetooth
systemctl stop hciuart
systemctl disable hciuart
echo "dtoverlay=disable-bt" >> /boot/config.txt

# Enable 1-Wire for temperature sensors
echo "dtoverlay=w1-gpio" >> /boot/config.txt

# Set GPU memory to minimum (16MB for headless)
echo "gpu_mem=16" >> /boot/config.txt

success "Hardware interfaces configured"

# ==============================================================================
# WiFi Configuration
# ==============================================================================

info "Configuring WiFi..."

# Create wpa_supplicant configuration
cat > /etc/wpa_supplicant/wpa_supplicant.conf <<EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

network={
    ssid="$WIFI_SSID"
    psk="$WIFI_PASS"
    key_mgmt=WPA-PSK
    scan_ssid=1
}
EOF

# Fix permissions
chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf

success "WiFi configured for SSID: $WIFI_SSID"

# ==============================================================================
# Power Optimization
# ==============================================================================

info "Applying power optimizations for solar operation..."

# Disable HDMI (saves ~25mA)
info "Disabling HDMI output..."
/usr/bin/tvservice -o 2>/dev/null || true

# Add to crontab to disable on boot
echo "@reboot /usr/bin/tvservice -o" | crontab -

# Disable unnecessary services
info "Disabling power-hungry services..."
systemctl disable --now bluetooth 2>/dev/null || true
systemctl disable --now avahi-daemon 2>/dev/null || true
systemctl disable --now triggerhappy 2>/dev/null || true
systemctl disable --now ModemManager 2>/dev/null || true

# Configure power saving for WiFi
info "Configuring WiFi power saving..."
cat > /etc/network/interfaces.d/wlan0 <<EOF
allow-hotplug wlan0
iface wlan0 inet dhcp
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf
    wireless-power off
EOF

# Enable watchdog for automatic reboots
info "Enabling hardware watchdog..."
apt-get install -y watchdog
systemctl enable watchdog
echo "dtparam=watchdog=on" >> /boot/config.txt

success "Power optimizations applied"

# ==============================================================================
# Timezone and NTP
# ==============================================================================

info "Setting timezone to $TIMEZONE..."
timedatectl set-timezone "$TIMEZONE"

# Ensure NTP is working
systemctl enable ntp
systemctl restart ntp

# Set hardware clock
hwclock --systohc

success "Timezone set to $TIMEZONE"

# ==============================================================================
# Install Python Dependencies
# ==============================================================================

info "Installing Python packages..."

# Create virtual environment for isolation
mkdir -p /opt/mycosentinel
python3 -m venv /opt/mycosentinel/venv
source /opt/mycosentinel/venv/bin/activate

# Upgrade pip
pip install --upgrade pip wheel setuptools

# Install core dependencies for sensor operation
pip install \
    RPi.GPIO \
    smbus2 \
    adafruit-circuitpython-ads1x15 \
    adafruit-blinka \
    adafruit-circuitpython-dht \
    picamera2 \
    paho-mqtt \
    numpy \
    scipy \
    pandas \
    influxdb-client \
    pyserial \
    schedule \
    pyyaml \
    requests

# Install optional ML packages (comment out if needed to save space)
# pip install scikit-learn tensorflow-lite

deactivate

success "Python dependencies installed"

# ==============================================================================
# Clone and Install MycoSentinel Software
# ==============================================================================

info "Installing MycoSentinel software..."

if [[ -n "$GIT_REPO" ]]; then
    # Clone from git
    if [[ -d /opt/mycosentinel/src ]]; then
        rm -rf /opt/mycosentinel/src
    fi
    git clone --depth 1 --branch "$GIT_BRANCH" "$GIT_REPO" /opt/mycosentinel/src
else
    # Use bundled software
    info "Using bundled software..."
    mkdir -p /opt/mycosentinel/src
fi

# Create symlink for module imports
ln -sf /opt/mycosentinel/src/src/mycosentinel /opt/mycosentinel/venv/lib/python3.11/site-packages/mycosentinel 2>/dev/null || true

success "MycoSentinel software installed"

# ==============================================================================
# Create Configuration Files
# ==============================================================================

info "Creating configuration files..."

# Create node configuration
mkdir -p /opt/mycosentinel/config

cat > /opt/mycosentinel/config/node_config.yaml <<EOF
# MycoSentinel Node Configuration
# Auto-generated by node_provision.sh

node:
  id: "$NODE_ID"
  location:
    name: "Field Deployment"
    lat: 0.0  # Set during calibration
    lon: 0.0  # Set during calibration
  
hardware:
  use_mock: false
  i2c_bus: 1
  
  # ADS1115 ADC addresses
  adc_addresses:
    - 0x48
    - 0x49
  
  # GPIO pin assignments (BCM numbering)
  pins:
    heater_pwm: 18
    mist_solenoid: 23
    growth_led: 24
    detection_led: 25
    dht_data: 2
    temp_1wire: 16
    camera_led: 21
  
  # Camera settings
  camera:
    resolution: [640, 480]
    framerate: 5
    awb_mode: "fluorescent"  # For GFP detection

sampling:
  rate_hz: 0.1  # 1 reading every 10 seconds
  burst_mode: false
  burst_count: 10
  burst_interval_sec: 60

bioreactor:
  target_temp_c: 28.0
  temp_tolerance: 1.0
  heater_duty_max: 0.8
  mist_interval_hours: 4
  mist_duration_sec: 5

network:
  mqtt:
    enabled: true
    broker: "$GATEWAY_IP"
    port: 1883
    username: "$MQTT_USER"
    password: "$MQTT_PASS"
    client_id: "$NODE_ID"
    keepalive: 60
    topic_data: "mycosentinel/nodes/$NODE_ID/data"
    topic_status: "mycosentinel/nodes/$NODE_ID/status"
    topic_cmd: "mycosentinel/nodes/$NODE_ID/cmd"
    qos: 1
    
  http:
    enabled: false
    endpoint: ""
    timeout: 5

logging:
  level: "INFO"
  file: "/var/log/mycosentinel/$NODE_ID.log"
  max_size_mb: 10
  backup_count: 3
  
  # Remote log shipping (optional)
  remote:
    enabled: false
    endpoint: ""

power:
  low_battery_threshold_v: 3.3
  critical_battery_threshold_v: 3.1
  auto_shutdown_on_critical: true
  solar_mode: true
  
  # Power saving schedule
  sleep_hours: [23, 0, 1, 2, 3, 4, 5]  # Deep sleep at night

# Initial calibration values (will be updated during field calibration)
calibration:
  optical:
    baseline_mean: 2000
    baseline_std: 50
    last_calibrated: null
  temperature:
    offset: 0.0
    scale: 1.0
EOF

# Create startup script
cat > /opt/mycosentinel/start_node.sh <<'EOFSCRIPT'
#!/bin/bash
# MycoSentinel Node Startup Script

NODE_ID="${1:-node01}"
CONFIG_FILE="/opt/mycosentinel/config/node_config.yaml"
LOG_FILE="/var/log/mycosentinel/${NODE_ID}.log"
PID_FILE="/var/run/mycosentinel.pid"

# Create log directory
mkdir -p /var/log/mycosentinel
mkdir -p /opt/mycosentinel/data

# Activate virtual environment
source /opt/mycosentinel/venv/bin/activate

# Export Python path
export PYTHONPATH="/opt/mycosentinel/src/src:$PYTHONPATH"

# Check if already running
if [[ -f "$PID_FILE" ]] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "MycoSentinel is already running (PID: $(cat $PID_FILE))"
    exit 1
fi

echo "Starting MycoSentinel node: $NODE_ID"
echo "Config: $CONFIG_FILE"
echo "Log: $LOG_FILE"

# Run the main sensor loop
exec python3 -m mycosentinel.main \
    --config "$CONFIG_FILE" \
    --node-id "$NODE_ID" \
    >> "$LOG_FILE" 2>&1 &

# Save PID
echo $! > "$PID_FILE"

echo "Started with PID: $(cat $PID_FILE)"
EOFSCRIPT

chmod +x /opt/mycosentinel/start_node.sh

# Create shutdown script
cat > /opt/mycosentinel/stop_node.sh <<'EOFSCRIPT'
#!/bin/bash
PID_FILE="/var/run/mycosentinel.pid"

if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping MycoSentinel (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Stopped"
    else
        echo "MycoSentinel is not running"
        rm -f "$PID_FILE"
    fi
else
    echo "PID file not found. Is MycoSentinel running?"
    # Try to find and kill Python processes
    pkill -f "mycosentinel.main" 2>/dev/null || true
    echo "Sent termination signal to any mycosentinel processes"
fi
EOFSCRIPT

chmod +x /opt/mycosentinel/stop_node.sh

cat > /opt/mycosentinel/status.sh <<'EOFSCRIPT'
#!/bin/bash
PID_FILE="/var/run/mycosentinel.pid"
CONFIG_FILE="/opt/mycosentinel/config/node_config.yaml"

echo "=== MycoSentinel Node Status ==="
echo ""

# Check if running
if [[ -f "$PID_FILE" ]] && kill -0 $(cat "$PID_FILE") 2>/dev/null; then
    echo "Status: RUNNING (PID: $(cat $PID_FILE))"
else
    echo "Status: STOPPED"
fi

echo ""
echo "=== System Info ==="
echo "Hostname: $(hostname)"
echo "IP Address: $(hostname -I | awk '{print $1}')"
echo "Uptime: $(uptime -p)"
echo "Load: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"

# Check temperature if available
if [[ -f /sys/class/thermal/thermal_zone0/temp ]]; then
    TEMP=$(cat /sys/class/thermal/thermal_zone0/temp)
    echo "CPU Temp: $((TEMP / 1000)).$((TEMP % 1000 / 100))°C"
fi

# Check I2C devices if i2c-tools installed
if command -v i2cdetect &> /dev/null; then
    echo ""
    echo "=== I2C Devices ==="
    i2cdetect -y 1 2>/dev/null | grep -v "^\s" | tail -n +2 || echo "No I2C bus found"
fi

# Check recent log
echo ""
echo "=== Recent Log Entries ==="
if [[ -d /var/log/mycosentinel ]]; then
    LOG_FILE=$(ls -t /var/log/mycosentinel/*.log 2>/dev/null | head -1)
    if [[ -n "$LOG_FILE" ]]; then
        tail -5 "$LOG_FILE" 2>/dev/null || echo "No log entries yet"
    fi
fi

echo ""
echo "=== Recent MQTT Activity ==="
tail -5 /var/log/mycosentinel/mqtt_activity.log 2>/dev/null || echo "No MQTT activity logged"
EOFSCRIPT

chmod +x /opt/mycosentinel/status.sh

success "Configuration files created"

# ==============================================================================
# Systemd Service
# ==============================================================================

info "Creating systemd service..."

cat > /etc/systemd/system/mycosentinel.service <<EOF
[Unit]
Description=MycoSentinel Biosensor Node
After=network.target time-sync.target
Wants=network.target time-sync.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/mycosentinel
Environment=PYTHONPATH=/opt/mycosentinel/src/src
Environment=NODE_CONFIG=/opt/mycosentinel/config/node_config.yaml

# Start the node
ExecStart=/opt/mycosentinel/venv/bin/python3 -m mycosentinel.main --config /opt/mycosentinel/config/node_config.yaml --node-id $NODE_ID

# Graceful shutdown
ExecStop=/bin/kill -TERM \$MAINPID
TimeoutStopSec=30

# Restart on failure
Restart=on-failure
RestartSec=10

# Security
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/var/log/mycosentinel /opt/mycosentinel/data

# Resource limits
MemoryMax=512M
CPUQuota=50%

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload
systemctl enable mycosentinel.service

success "Systemd service created and enabled"

# ==============================================================================
# Log Rotation
# ==============================================================================

info "Configuring log rotation..."

cat > /etc/logrotate.d/mycosentinel <<EOF
/var/log/mycosentinel/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 pi pi
    sharedscripts
    postrotate
        systemctl reload rsyslog > /dev/null 2>&1 || true
    endscript
}
EOF

mkdir -p /var/log/mycosentinel
chown pi:pi /var/log/mycosentinel

success "Log rotation configured"

# ==============================================================================
# Hardware Test Script
# ==============================================================================

info "Creating hardware test script..."

cat > /opt/mycosentinel/test_hardware.py <<'EOFPYTHON'
#!/usr/bin/env python3
"""
Hardware test script for MycoSentinel nodes
Run after provisioning to verify all components
"""

import sys
import time
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

print("=" * 60)
print("MYCOSENTINEL HARDWARE TEST")
print("=" * 60)

errors = []
warnings = []

# Test I2C
print("\n[1/8] Testing I2C bus...")
try:
    i2c = busio.I2C(board.SCL, board.SDA)
    print("  ✓ I2C bus initialized")
    
    # Scan for devices
    while not i2c.try_lock():
        pass
    devices = i2c.scan()
    i2c.unlock()
    
    print(f"  Found I2C devices: {[hex(d) for d in devices]}")
    if 0x48 in devices:
        print("  ✓ ADS1115 (0x48) detected")
    else:
        warnings.append("ADS1115 at 0x48 not found")
    if 0x49 in devices:
        print("  ✓ ADS1115 (0x49) detected")
except Exception as e:
    errors.append(f"I2C test failed: {e}")
    print(f"  ✗ I2C error: {e}")

# Test ADC
print("\n[2/8] Testing ADS1115 ADC...")
try:
    ads = ADS.ADS1115(i2c)
    chan = AnalogIn(ads, ADS.P0)
    print(f"  ✓ ADC reading: {chan.voltage:.3f}V")
except Exception as e:
    errors.append(f"ADC test failed: {e}")
    print(f"  ✗ ADC error: {e}")

# Test GPIO
print("\n[3/8] Testing GPIO pins...")
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    
    test_pins = [18, 23, 24, 25]
    for pin in test_pins:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        time.sleep(0.1)
        GPIO.output(pin, GPIO.LOW)
    GPIO.cleanup()
    print(f"  ✓ GPIO pins {test_pins} working")
except Exception as e:
    warnings.append(f"GPIO test: {e}")
    print(f"  ⚠ GPIO: {e}")

# Test Camera
print("\n[4/8] Testing camera...")
try:
    from picamera2 import Picamera2
    picam2 = Picamera2()
    config = picam2.create_still_configuration()
    picam2.configure(config)
    picam2.start()
    time.sleep(2)
    picam2.capture_file("/tmp/test_capture.jpg")
    picam2.stop()
    print("  ✓ Camera captured test image to /tmp/test_capture.jpg")
except Exception as e:
    warnings.append(f"Camera test: {e}")
    print(f"  ⚠ Camera: {e}")

# Test 1-Wire Temperature
print("\n[5/8] Testing 1-Wire temperature sensor...")
try:
    import glob
    base_dir = '/sys/bus/w1/devices/'
    device_folders = glob.glob(base_dir + '28*')
    if device_folders:
        device_file = device_folders[0] + '/w1_slave'
        with open(device_file, 'r') as f:
            lines = f.readlines()
            if lines[0].strip()[-3:] == 'YES':
                equals_pos = lines[1].find('t=')
                temp = float(lines[1][equals_pos+2:]) / 1000.0
                print(f"  ✓ Temperature sensor: {temp:.2f}°C")
            else:
                warnings.append("Temperature sensor: CRC error")
    else:
        warnings.append("No 1-Wire devices found")
except Exception as e:
    warnings.append(f"Temperature sensor: {e}")
    print(f"  ⚠ Temperature: {e}")

# Test DHT22 (if connected)
print("\n[6/8] Testing DHT22 humidity sensor...")
try:
    import adafruit_dht
    dht_device = adafruit_dht.DHT22(board.D4)  # GPIO4
    temperature = dht_device.temperature
    humidity = dht_device.humidity
    print(f"  ✓ DHT22: {temperature:.1f}°C, {humidity:.1f}%")
except Exception as e:
    warnings.append(f"DHT22 not detected: {e}")
    print(f"  ⚠ DHT22: {e}")

# Test MQTT Connection
print("\n[7/8] Testing MQTT connection...")
try:
    import paho.mqtt.client as mqtt
    client = mqtt.Client()
    # Try to connect to localhost first
    client.connect("localhost", 1883, 5)
    client.disconnect()
    print("  ✓ MQTT connection successful")
except Exception as e:
    warnings.append(f"MQTT not available: {e}")
    print(f"  ⚠ MQTT: {e}")

# Test Network
print("\n[8/8] Testing network connectivity...")
import socket
try:
    socket.create_connection(("8.8.8.8", 53), timeout=3)
    print("  ✓ Internet connectivity OK")
except:
    print("  ⚠ No internet (may be OK for offline mode)")

# Summary
print("\n" + "=" * 60)
print("TEST SUMMARY")
print("=" * 60)
if errors:
    print(f"\n❌ {len(errors)} ERROR(s):")
    for e in errors:
        print(f"   - {e}")
if warnings:
    print(f"\n⚠️  {len(warnings)} WARNING(s):")
    for w in warnings:
        print(f"   - {w}")
if not errors and not warnings:
    print("\n✅ All tests passed!")

print("\n" + "=" * 60)
print("Run 'sudo systemctl start mycosentinel' to start the node")
print("Run '/opt/mycosentinel/status.sh' to check status")
print("=" * 60)

sys.exit(1 if errors else 0)
EOFPYTHON

chmod +x /opt/mycosentinel/test_hardware.py
chown -R pi:pi /opt/mycosentinel

success "Hardware test script created"

# ==============================================================================
# Final Setup
# ==============================================================================

info "Applying final configuration..."

# Set permissions
chown -R pi:pi /opt/mycosentinel
chmod 755 /opt/mycosentinel

# Create data directory
mkdir -p /opt/mycosentinel/data
chown pi:pi /opt/mycosentinel/data

# Create MOTD
cat > /etc/update-motd.d/99-mycosentinel <<EOF
#!/bin/bash
echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║           🍄 MYCOSENTINEL BIOSENSOR NODE 🍄                ║"
echo "╠════════════════════════════════════════════════════════════╣"
echo "║  Node ID:   $NODE_ID                                        ║"
echo "║  Gateway:   $GATEWAY_IP                                     ║"
echo "║  Config:    /opt/mycosentinel/config/node_config.yaml       ║"
echo "║  Commands:  sudo systemctl {start|stop|status} mycosentinel ║"
echo "║             /opt/mycosentinel/test_hardware.py              ║"
echo "║             /opt/mycosentinel/status.sh                     ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
EOF

chmod +x /etc/update-motd.d/99-mycosentinel

success "Final configuration applied"

# ==============================================================================
# Summary and Reboot
# ==============================================================================

success "Provisioning complete!"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "                    PROVISIONING SUMMARY                    "
echo "════════════════════════════════════════════════════════════"
echo ""
echo "Node ID:        $NODE_ID"
echo "Gateway IP:     $GATEWAY_IP"
echo "WiFi Network:   $WIFI_SSID"
echo "Timezone:       $TIMEZONE"
echo ""
echo "Installation Directory: /opt/mycosentinel"
echo "Configuration File:     /opt/mycosentinel/config/node_config.yaml"
echo "Log Directory:          /var/log/mycosentinel"
echo "Service Name:           mycosentinel"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "                      NEXT STEPS                           "
echo "════════════════════════════════════════════════════════════"
echo ""
echo "1. Review configuration:"
echo "   sudo nano /opt/mycosentinel/config/node_config.yaml"
echo ""
echo "2. Update WiFi credentials if needed:"
echo "   sudo nano /etc/wpa_supplicant/wa_supplicant.conf"
echo ""
echo "3. Test hardware before deployment:"
echo "   python3 /opt/mycosentinel/test_hardware.py"
echo ""
echo "4. Start the service:"
echo "   sudo systemctl start mycosentinel"
echo ""
echo "5. Check status:"
echo "   sudo systemctl status mycosentinel"
echo "   /opt/mycosentinel/status.sh"
echo ""
echo "════════════════════════════════════════════════════════════"
echo ""

# Ask about reboot
read -p "Reboot now to apply all changes? [Y/n]: " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    info "Rebooting in 5 seconds..."
    sleep 5
    reboot
else
    warning "Reboot later with: sudo reboot"
fi