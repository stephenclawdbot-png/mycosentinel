# MycoSentinel Deployment Infrastructure

Complete deployment package for field-ready biosensor networks.

## 📦 Contents

```
deployment/
├── DEPLOYMENT_GUIDE.md        # Complete field deployment manual
├── docker-compose.yml         # Gateway stack (MQTT + InfluxDB + Grafana)
├── node_provision.sh          # Automated Pi Zero provisioning
├── mosquitto/
│   └── config/
│       ├── mosquitto.conf     # MQTT broker configuration
│       └── acl                # Access control rules
├── telegraf/
│   └── telegraf.conf          # Data ingestion config
├── grafana/
│   ├── provisioning/
│   │   ├── dashboards/
│   │   │   └── dashboard.yml  # Dashboard provider config
│   │   └── datasources/
│   │       └── datasource.yml # InfluxDB datasource config
│   └── dashboards/
│       └── mycosentinel-main.json  # Main dashboard
└── README.md                  # This file
```

## 🚀 Quick Start

### 1. Gateway Setup (30 min)

```bash
# On Raspberry Pi 4/5 (gateway node)
cd ~/deployment

# Start the stack
docker-compose up -d

# View logs
docker-compose logs -f

# Access services:
# - Dashboard: http://192.168.1.100:3000 (admin/change_me)
# - MQTT: 192.168.1.100:1883
# - Node-RED: http://192.168.1.100:1880
```

### 2. Node Provisioning (per node, 20 min)

```bash
# On Raspberry Pi Zero 2 W (sensor node)
# Either download and run locally, or use curl:

export NODE_ID="node01"
export GATEWAY_IP="192.168.1.100"
export WIFI_SSID="YourWiFi"
export WIFI_PASS="YourPassword"

curl -fsSL https://raw.githubusercontent.com/yourrepo/mycosentinel/main/deployment/node_provision.sh | sudo bash
```

### 3. Field Deployment

Follow the [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for:
- Network topology
- Physical assembly
- Calibration procedures
- Solar power integration

## 🔒 Security Notes

**IMPORTANT:** Before deploying:

1. Change default passwords:
   - Grafana: `admin` / `mycosentinel_grafana_pass`
   - InfluxDB: `admin` / `mycosentinel_admin_pass`
   - MQTT: Generate password file with `mosquitto_passwd`

2. Generate MQTT passwords:
   ```bash
   docker exec -it mycosentinel-mosquitto mosquitto_passwd -c /mosquitto/config/passwd gateway
   docker exec -it mycosentinel-mosquitto mosquitto_passwd /mosquitto/config/passwd node01
   docker exec -it mycosentinel-mosquitto mosquitto_passwd /mosquitto/config/passwd node02
   # ... etc
   ```

3. Update `docker-compose.yml` environment variables with secure passwords

## 📊 Monitoring

After deployment, access:
- **Dashboard**: `http://GATEWAY_IP:3000`
- **Node Status**: Run `/opt/mycosentinel/status.sh` on any node
- **Logs**: `docker-compose logs` or `/var/log/mycosentinel/`

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Node won't connect to WiFi | Check `/etc/wpa_supplicant/wpa_supplicant.conf` |
| MQTT connection fails | Verify mosquitto is running: `docker-compose ps` |
| No data in Grafana | Check Telegraf logs: `docker-compose logs telegraf` |
| Low battery on nodes | Reduce sampling rate in `node_config.yaml` |

## 📞 Support

- Issues: [GitHub Issues](https://github.com/yourrepo/mycosentinel/issues)
- Documentation: See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Hardware specs: See `hardware/` directory in main repo

---

**Build it. Deploy it. Monitor everything.** 🍄