# 🐳 Docker Quick Reference

## One-Command Start
```bash
./docker-start.sh
```

## Essential Commands

### Start/Stop
```bash
docker-compose up -d              # Start in background
docker-compose down               # Stop all
docker-compose restart            # Restart all
```

### Logs
```bash
docker-compose logs -f            # All logs
docker-compose logs -f commentator # App logs only
```

### Database
```bash
# Enter MySQL
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket

# Quick queries
docker-compose exec mysql mysql -uroot -pyour_mysql_password IndoorCricket -e "SELECT * FROM DeliveryAudio LIMIT 5;"
```

### Container Access
```bash
docker-compose exec commentator bash   # Enter app container
docker-compose exec mysql bash          # Enter DB container
```

## Environment Setup
```bash
# Copy template
cp .env.example .env

# Required: Add your API key
echo "ELEVENLABS_API_KEY=sk_your_key_here" >> .env

# Start
./docker-start.sh
```

## File Locations
- **Audio Output**: `./audio/`
- **Logs**: `./logs/`
- **Database Data**: Docker volume `mysql_data`

## Troubleshooting
```bash
# Rebuild everything
docker-compose build --no-cache
docker-compose up -d

# View all logs
docker-compose logs

# Clean restart
docker-compose down -v
docker-compose up -d
```

## Complete Cleanup
```bash
docker-compose down -v --rmi all
docker system prune -af
```
