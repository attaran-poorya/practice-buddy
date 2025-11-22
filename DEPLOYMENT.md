# Deployment Guide

## Server Options

### Option 1: Cloud VM (Recommended for production)

**Providers:**
- **AWS EC2**: Most popular, free tier available
- **DigitalOcean Droplet**: Simple, good for beginners ($6/month)
- **Google Cloud Compute Engine**: Free tier, good integration
- **Hetzner**: Cheapest option in Europe (~€4/month)

**Minimum Requirements:**
- 2GB RAM (for audio processing)
- 1 CPU core
- 20GB storage
- Ubuntu 22.04 or later

### Option 2: Always-on Home Server/Raspberry Pi

If you have reliable internet and a spare computer.

---

## Deployment Steps (Ubuntu Server)

### 1. Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and dependencies
sudo apt install python3.11 python3.11-venv python3-pip git -y

# Install system libraries for audio processing
sudo apt install libsndfile1 ffmpeg -y
```

### 2. Clone Repository

```bash
# Create app directory
mkdir -p ~/apps
cd ~/apps

# Clone your repository
git clone <your-repo-url> practicebuddy-bot
cd practicebuddy-bot
```

### 3. Setup Python Environment

```bash
# Create virtual environment
python3.11 -m venv venv

# Activate
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
# Create .env file
nano .env

# Add your bot token:
TELEGRAM_BOT_TOKEN=your_actual_token_here

# Save and exit (Ctrl+X, Y, Enter)
```

### 5. Test Run

```bash
python bot.py
```

If it starts successfully, proceed to make it run permanently.

---

## Running as a Service (systemd)

### 1. Create Service File

```bash
sudo nano /etc/systemd/system/practicebuddy-bot.service
```

### 2. Add Service Configuration

```ini
[Unit]
Description=Practice Buddy Telegram Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/apps/practicebuddy-bot
Environment="PATH=/home/your_username/apps/practicebuddy-bot/venv/bin"
ExecStart=/home/your_username/apps/practicebuddy-bot/venv/bin/python bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Replace `your_username` with your actual username!**

### 3. Enable and Start Service

```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable practicebuddy-bot

# Start service
sudo systemctl start practicebuddy-bot

# Check status
sudo systemctl status practicebuddy-bot
```

### 4. Useful Service Commands

```bash
# View logs
sudo journalctl -u practicebuddy-bot -f

# Restart service
sudo systemctl restart practicebuddy-bot

# Stop service
sudo systemctl stop practicebuddy-bot
```

---

## Deployment with Git Workflow

### Initial Setup

```bash
# On your local machine
cd "C:\Poorya\Rapid Projects\practicebuddy bot"

# Initialize git (if not already done)
git init

# Add files
git add .
git commit -m "Initial commit: v0.1.0"

# Add remote (GitHub/GitLab)
git remote add origin <your-repo-url>
git push -u origin main
```

### Updating Server

```bash
# SSH into server
ssh user@your-server-ip

# Navigate to app
cd ~/apps/practicebuddy-bot

# Pull latest changes
git pull origin main

# Update dependencies if needed
source venv/bin/activate
pip install -r requirements.txt

# Restart service
sudo systemctl restart practicebuddy-bot
```

---

## Monitoring and Maintenance

### View Logs

```bash
# Real-time logs
sudo journalctl -u practicebuddy-bot -f

# Last 100 lines
sudo journalctl -u practicebuddy-bot -n 100

# Logs from today
sudo journalctl -u practicebuddy-bot --since today
```

### Disk Space Management

```bash
# Check disk usage
df -h

# Clean old voice messages (be careful!)
cd ~/apps/practicebuddy-bot/voice_messages
find . -name "*.ogg" -mtime +7 -delete  # Delete files older than 7 days
find . -name "*.png" -mtime +7 -delete
```

### Automatic Cleanup (Optional)

Create a cron job:

```bash
# Edit crontab
crontab -e

# Add line to clean files weekly (Sundays at 2 AM)
0 2 * * 0 find ~/apps/practicebuddy-bot/voice_messages -name "*.ogg" -mtime +7 -delete
0 2 * * 0 find ~/apps/practicebuddy-bot/voice_messages -name "*.png" -mtime +7 -delete
```

---

## Security Considerations

1. **Never commit .env file** (already in .gitignore)
2. **Use SSH keys** for server access, not passwords
3. **Setup firewall**:
   ```bash
   sudo ufw allow 22/tcp  # SSH
   sudo ufw enable
   ```
4. **Keep system updated**:
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```
5. **Limit bot token exposure** - rotate if compromised

---

## Cost Estimates

**DigitalOcean Droplet (Recommended for beginners):**
- $6/month for 1GB RAM
- $12/month for 2GB RAM (recommended)

**AWS EC2:**
- Free tier: 750 hours/month for 12 months (1GB RAM)
- After: ~$8-10/month

**Hetzner (Europe):**
- €4.15/month for 2GB RAM (cheapest option)

---

## Troubleshooting

### Bot not responding

```bash
# Check if service is running
sudo systemctl status practicebuddy-bot

# Check logs for errors
sudo journalctl -u practicebuddy-bot -n 50
```

### Out of memory

Upgrade server or add swap:

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

### Audio processing fails

```bash
# Reinstall audio libraries
sudo apt install --reinstall libsndfile1 ffmpeg
```

---

## Next Steps After Deployment

1. Test bot thoroughly on server
2. Monitor logs for first few days
3. Set up automated backups of `.env` file
4. Consider adding error notifications (e.g., to your Telegram)
5. Document any custom configurations