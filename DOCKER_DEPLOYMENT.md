# 🐳 Docker Deployment - Complete Package

## ✅ What's Included

Your cricket commentary system is now **fully Dockerized** with:

### Docker Files Created
- ✅ **Dockerfile** - Application container image
- ✅ **docker-compose.yml** - Multi-container orchestration (MySQL + App)
- ✅ **docker-init.sql** - Database auto-initialization
- ✅ **docker-start.sh** - One-command deployment script
- ✅ **test-docker.sh** - Deployment validation
- ✅ **.dockerignore** - Build optimization
- ✅ **entrypoint.sh** - Container startup script

### Features
- 🐳 **Complete Isolation**: No system dependencies needed
- 🔄 **Auto Database Setup**: MySQL initialized with tables & sample data
- 🎯 **Environment-Based Config**: Pass API key as parameter
- 📦 **Portable**: Run on any system with Docker
- 🔒 **Volume Persistence**: Data survives container restarts
- 🚀 **One-Command Deploy**: `./docker-start.sh`

## 🚀 Quick Start (3 Steps)

### 1. Add Your API Key
```bash
# Copy environment template
cp .env.example .env

# Edit and add your ElevenLabs API key
nano .env
# Change: ELEVENLABS_API_KEY=sk_your_api_key_here
```

### 2. Run Deployment Script
```bash
chmod +x docker-start.sh
./docker-start.sh
```

### 3. Done! 🎉
```
✅ MySQL database running with sample data
✅ Commentary system running and polling
✅ Audio saved to ./audio/
✅ Logs saved to ./logs/
```

## 📋 System Requirements

- **Docker Engine**: 20.10+ 
- **Docker Compose**: 2.0+
- **Disk Space**: ~2GB (images + data)
- **RAM**: 1GB minimum, 2GB recommended

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Docker Network                       │
│  ┌──────────────────┐      ┌──────────────────┐    │
│  │  MySQL Container │      │ App Container     │    │
│  │  ─────────────── │      │ ───────────────   │    │
│  │  • Port: 3306    │◄────►│ • Python 3.11     │    │
│  │  • Database:     │      │ • All dependencies│    │
│  │    IndoorCricket │      │ • TTS + Audio     │    │
│  │  • Auto-init SQL │      │ • Main app        │    │
│  └──────────────────┘      └──────────────────┘    │
│         │                           │               │
│         │ Persistent Volume         │ Host Mounts   │
│         ▼                           ▼               │
└─────────────────────────────────────────────────────┘
          │                           │
          ▼                           ▼
    [mysql_data]              [./audio, ./logs]
```

## 📦 What Gets Created

### Containers
1. **cricket_mysql** - MySQL 8.0 database
   - Initialized with DeliveryAudio table
   - 6 sample commentary records
   - Persistent data volume

2. **cricket_commentator** - Application
   - Python 3.11 + all dependencies
   - TTS audio generation
   - Real-time commentary system

### Volumes & Files
```
project/
├── audio/           # Generated TTS audio files (mounted)
├── logs/            # Application logs (mounted)
└── docker volumes/
    └── mysql_data/  # Persistent database (Docker volume)
```

## 🔧 Configuration

### Environment Variables (.env)

**Required:**
```env
ELEVENLABS_API_KEY=sk_your_actual_key_here
```

**MySQL (Auto-configured for Docker):**
```env
MYSQL_HOST=mysql              # Container name
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=IndoorCricket
```

**Optional:**
```env
USE_DUMMY_MODE=false          # false = use real DB
SPEAK_ONLY_DELIVERIES=true    # Skip announcements
API_BASE_URL=http://...       # Backend API
```

## 🎮 Usage Commands

### Start/Stop
```bash
# Start everything
./docker-start.sh

# Or manually
docker compose up -d

# Stop
docker compose down

# Restart
docker compose restart
```

### Logs
```bash
# Watch all logs
docker compose logs -f

# Watch app only
docker compose logs -f commentator

# View MySQL logs
docker compose logs -f mysql
```

### Database Access
```bash
# Enter MySQL CLI
docker compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket

# Quick query
docker compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "SELECT audio_id, event_id, sentence, status FROM DeliveryAudio LIMIT 5;"

# Add new commentary
docker compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "INSERT INTO DeliveryAudio (delivery_id, event_id, match_id, sentence, intensity) 
   VALUES ('delivery-new', 100, 'match-001', 'Brilliant shot!', 'high');"
```

### Container Management
```bash
# Enter app container
docker compose exec commentator bash

# Check container status
docker compose ps

# View resource usage
docker stats

# Rebuild images
docker compose build --no-cache
```

## 🔄 Deploy on New System

### Complete Fresh Install
```bash
# 1. Copy project (or git clone)
cd cricket_comp/

# 2. Create .env with your API key
echo "ELEVENLABS_API_KEY=sk_your_key" > .env

# 3. Deploy
./docker-start.sh

# Done! System is running
```

### With Existing Database
```bash
# 1. Start with your data
docker compose up -d mysql

# 2. Import data
docker compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket < your_data.sql

# 3. Start app
docker compose up -d commentator
```

## 🧪 Testing

### Validate Setup
```bash
./test-docker.sh
```

### Check Everything Works
```bash
# 1. Start services
docker compose up -d

# 2. Check logs
docker compose logs commentator | grep "Connected"

# 3. Verify database
docker compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "SELECT COUNT(*) FROM DeliveryAudio;"

# 4. Check audio directory
ls -lh audio/
```

## 🛠️ Troubleshooting

### Container Won't Start
```bash
# View detailed logs
docker compose logs

# Check individual service
docker compose ps
docker compose logs mysql
docker compose logs commentator

# Restart specific service
docker compose restart commentator
```

### MySQL Connection Issues
```bash
# Check MySQL health
docker compose ps mysql

# View MySQL logs
docker compose logs mysql

# Test connection
docker compose exec commentator python3 -c \
  "import pymysql; print('OK') if pymysql.connect(host='mysql', user='root', password='your_mysql_password') else print('FAIL')"
```

### Audio Not Generating
```bash
# Check API key
docker compose exec commentator env | grep ELEVENLABS

# Check ffmpeg
docker compose exec commentator which ffmpeg

# Test TTS manually
docker compose exec commentator python3 -c \
  "from elevenlabs import generate; print('OK')"
```

### Permission Errors
```bash
# Fix audio/logs directories
sudo chown -R $USER:$USER audio logs
chmod 755 audio logs
```

### Complete Reset
```bash
# Stop and remove everything
docker compose down -v

# Remove images
docker compose down --rmi all

# Clean Docker system
docker system prune -af

# Fresh start
./docker-start.sh
```

## 📊 Monitoring

### Real-Time Logs
```bash
# Follow all logs
docker compose logs -f

# Filter for specific events
docker compose logs -f commentator | grep "sentence"
docker compose logs -f commentator | grep "audio_file_path"
```

### Resource Usage
```bash
# View stats
docker stats

# Detailed container info
docker inspect cricket_commentator
docker inspect cricket_mysql
```

### Health Checks
```bash
# Check service health
docker compose ps

# MySQL health
docker compose exec mysql mysqladmin ping -uroot -pyour_mysql_password

# App health (if endpoint exists)
curl http://localhost:8080/health
```

## 🚀 Advanced Usage

### Custom API Key via Command Line
```bash
# Pass as environment variable
ELEVENLABS_API_KEY=sk_your_key docker compose up -d

# Or in one command
docker compose run -e ELEVENLABS_API_KEY=sk_key commentator
```

### Scale Services (Multiple Instances)
```bash
# Run multiple commentator instances
docker compose up -d --scale commentator=3
```

### Connect to External Database
```bash
# Modify .env
MYSQL_HOST=192.168.1.100
MYSQL_PORT=3306

# Start without MySQL container
docker compose up -d commentator
```

### Custom Network Configuration
```bash
# Edit docker-compose.yml networks section
# Or use existing network
docker compose --network my_network up -d
```

## 📦 Deployment Checklist

Before deploying:
- [ ] Docker & Docker Compose installed
- [ ] `.env` file created with API key
- [ ] `downloads/crowd_of.wav` exists
- [ ] Ports 3306 and 8080 available
- [ ] Sufficient disk space (2GB+)

Deployment steps:
- [ ] Run `./test-docker.sh` to validate
- [ ] Run `./docker-start.sh` to deploy
- [ ] Check logs: `docker compose logs -f`
- [ ] Verify database: `docker compose exec mysql...`
- [ ] Test audio generation

## 🎯 Benefits

### ✅ Portability
- Run on Linux, macOS, Windows
- No manual dependency installation
- Consistent environment everywhere

### ✅ Isolation
- No conflicts with system packages
- Each container independent
- Clean uninstall (`docker compose down -v`)

### ✅ Scalability
- Easy horizontal scaling
- Load balancing ready
- Microservices architecture

### ✅ Maintainability
- Easy updates (`docker compose pull`)
- Version control of images
- Rollback capability

### ✅ Development
- Identical dev/prod environments
- Fast onboarding for new developers
- CI/CD ready

## 📚 Additional Resources

- **Docker Guide**: See `DOCKER_GUIDE.md`
- **Quick Reference**: See `DOCKER_QUICK_REF.md`
- **Compose File**: `docker-compose.yml`
- **Init SQL**: `docker-init.sql`

## 🎉 Success!

Your cricket commentary system is now:
- ✅ Fully containerized
- ✅ Database auto-configured
- ✅ Ready for any system
- ✅ Production-ready

**Deploy on any machine with just:** `./docker-start.sh` 🚀
