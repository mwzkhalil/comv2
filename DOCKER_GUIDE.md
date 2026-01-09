# 🐳 Docker Deployment Guide

## Quick Start (3 Steps)

### 1. Set Your API Key
```bash
# Copy environment template
cp .env.example .env

# Edit .env and add your ElevenLabs API key
nano .env
# Or use: ELEVENLABS_API_KEY=your_key_here
```

### 2. Run Docker Start Script
```bash
chmod +x docker-start.sh
./docker-start.sh
```

### 3. Done! 🎉
The system is now running in Docker containers.

## Manual Setup

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+

Install Docker: https://docs.docker.com/get-docker/

### Step-by-Step

#### 1. Configure Environment
```bash
# Create .env from template
cp .env.example .env

# Edit with your settings
nano .env
```

Required settings:
```env
ELEVENLABS_API_KEY=sk_your_api_key_here
MYSQL_PASSWORD=your_mysql_password
```

Optional settings:
```env
USE_DUMMY_MODE=false
SPEAK_ONLY_DELIVERIES=true
API_BASE_URL=http://your-backend-api:8000
```

#### 2. Build and Start
```bash
# Build images
docker-compose build

# Start services
docker-compose up -d

# View logs
docker-compose logs -f commentator
```

## Docker Architecture

### Services

#### 1. MySQL Container (`cricket_mysql`)
- **Image**: mysql:8.0
- **Port**: 3306
- **Database**: IndoorCricket
- **Auto-initialization**: Creates DeliveryAudio table with sample data
- **Volume**: Persistent data storage

#### 2. Commentator Container (`cricket_commentator`)
- **Base**: Python 3.11-slim
- **Dependencies**: All Python packages + ffmpeg
- **Volumes**: 
  - `./audio` → Generated audio files
  - `./logs` → Application logs
  - `./downloads` → Crowd sound effects

### Network
- Bridge network: `cricket_network`
- Internal DNS: Services communicate via container names

### Volumes
- `mysql_data`: Persistent MySQL database
- `./audio`: Audio output (host-mounted)
- `./logs`: Log files (host-mounted)

## Environment Variables

### MySQL Configuration
```env
MYSQL_HOST=mysql          # Container name (auto-resolved)
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=IndoorCricket
```

### ElevenLabs API
```env
ELEVENLABS_API_KEY=sk_***   # REQUIRED - Your API key
ELEVENLABS_VOICE_ID=PSk5... # Optional - Default voice
```

### Application Mode
```env
USE_DUMMY_MODE=false              # false = use real DB
SPEAK_ONLY_DELIVERIES=true        # Skip announcements
API_BASE_URL=http://backend:8000  # Backend API
```

## Docker Commands

### Basic Operations
```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart
docker-compose restart

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f commentator
docker-compose logs -f mysql
```

### Management
```bash
# Enter commentator container
docker-compose exec commentator bash

# Enter MySQL container
docker-compose exec mysql bash

# Run MySQL client
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket

# Check container status
docker-compose ps

# View resource usage
docker stats
```

### Database Operations
```bash
# View DeliveryAudio table
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "SELECT audio_id, event_id, sentence, status FROM DeliveryAudio LIMIT 5;"

# Check table counts
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "SELECT COUNT(*) FROM DeliveryAudio;"

# Add new commentary
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e \
  "INSERT INTO DeliveryAudio (delivery_id, event_id, match_id, sentence, intensity) 
   VALUES ('new-delivery', 100, 'match-001', 'Amazing shot!', 'high');"
```

### Cleanup
```bash
# Stop and remove containers
docker-compose down

# Remove containers and volumes (WARNING: deletes all data)
docker-compose down -v

# Remove images
docker-compose down --rmi all

# Full cleanup
docker-compose down -v --rmi all
docker system prune -af
```

## File Structure

```
cricket_comp/
├── Dockerfile              # Application container image
├── docker-compose.yml      # Multi-container orchestration
├── docker-init.sql         # MySQL initialization script
├── docker-start.sh         # Quick start script
├── .dockerignore           # Files to exclude from image
├── .env                    # Environment variables (create from .env.example)
├── .env.example            # Environment template
├── requirements.txt        # Python dependencies
├── main.py                 # Application entry point
├── config.py               # Configuration loader
├── database.py             # Database manager
├── audio_manager.py        # TTS and playback
├── commentary.py           # Commentary generator
├── downloads/              # Crowd sound effects
│   └── crowd_of.wav
├── audio/                  # Generated audio (mounted volume)
└── logs/                   # Application logs (mounted volume)
```

## Deployment on New System

### Complete Setup
```bash
# 1. Clone or copy project
git clone <repo> cricket_comp
cd cricket_comp

# 2. Set API key
echo "ELEVENLABS_API_KEY=sk_your_key" > .env

# 3. Start everything
./docker-start.sh
```

That's it! The system runs completely isolated in Docker.

## Troubleshooting

### MySQL Connection Failed
```bash
# Check if MySQL is healthy
docker-compose ps

# View MySQL logs
docker-compose logs mysql

# Restart MySQL
docker-compose restart mysql
```

### Audio Not Generating
```bash
# Check API key
docker-compose exec commentator env | grep ELEVENLABS

# View commentator logs
docker-compose logs -f commentator

# Check if ffmpeg is installed
docker-compose exec commentator which ffmpeg
```

### Permission Issues
```bash
# Fix audio directory permissions
chmod 777 audio logs

# Or run with sudo (not recommended for production)
sudo docker-compose up -d
```

### Container Won't Start
```bash
# View full logs
docker-compose logs

# Rebuild images
docker-compose build --no-cache

# Check Docker status
docker info
```

### Database Not Initialized
```bash
# Check initialization logs
docker-compose logs mysql | grep init

# Manually run init script
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket < docker-init.sql
```

## Production Considerations

### Security
```bash
# Use Docker secrets for sensitive data
echo "sk_your_key" | docker secret create elevenlabs_key -

# Update docker-compose.yml to use secrets
```

### Performance
```bash
# Allocate resources in docker-compose.yml
services:
  commentator:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
```

### Monitoring
```bash
# Use health checks
docker-compose ps
docker inspect cricket_commentator

# Export logs to external system
docker-compose logs --no-log-prefix | your-log-aggregator
```

## Benefits of Docker Deployment

✅ **Portability**: Run on any system with Docker  
✅ **Isolation**: No dependency conflicts  
✅ **Consistency**: Same environment everywhere  
✅ **Easy Updates**: `docker-compose pull && docker-compose up -d`  
✅ **Rollback**: Keep old images for quick rollback  
✅ **Scaling**: Easy to add more instances  

## Next Steps

1. **Production Deployment**: Use Docker Swarm or Kubernetes
2. **CI/CD**: Automate builds and deployments
3. **Monitoring**: Add Prometheus/Grafana
4. **Backup**: Automate MySQL backups

Your cricket commentary system is now fully Dockerized! 🚀
