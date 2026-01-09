#!/bin/bash
# Quick start script for Docker deployment

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║      Cricket Commentary System - Docker Quick Start                 ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed!"
    echo "   Install from: https://docs.docker.com/get-docker/"
    exit 1
fi

# Use docker compose (plugin) if available, otherwise docker-compose
COMPOSE_CMD="docker compose"
if ! docker compose version &> /dev/null 2>&1; then
    if command -v docker-compose &> /dev/null; then
        COMPOSE_CMD="docker-compose"
    else
        echo "❌ Docker Compose is not installed!"
        echo "   Install from: https://docs.docker.com/compose/install/"
        exit 1
    fi
fi
echo "✅ Docker and Docker Compose are installed"

# Check for .env file
if [ ! -f .env ]; then
    echo
    echo "⚠️  .env file not found. Creating from template..."
    cp .env.example .env
    echo "✅ Created .env file"
    echo
    echo "📝 IMPORTANT: Edit .env and add your ElevenLabs API key:"
    echo "   ELEVENLABS_API_KEY=your_api_key_here"
    echo
    read -p "Press Enter to continue after adding your API key, or Ctrl+C to exit..."
fi

# Validate API key
if ! grep -q "ELEVENLABS_API_KEY=sk_" .env 2>/dev/null; then
    echo
    echo "⚠️  WARNING: ElevenLabs API key not set in .env file"
    echo "   The system may not generate audio without a valid API key"
    echo
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting. Please add your API key to .env and try again."
$COMPOSE_CMD build

echo
echo "🚀 Starting services..."
$COMPOSE_CMD up -d

echo
echo "⏳ Waiting for services to be healthy..."
sleep 5

# Check if containers are running
if $COMPOSE_CMD ps | grep -q "Up"; then
    echo "✅ Services are running!"
    echo
    echo "📊 Container Status:"
    $COMPOSE_CMD
# Check if containers are running
if docker-compose ps | grep -q "Up"; then
    echo "✅ Services are running!"
    echo
    echo "📊 Container Status:"
    docker-compose ps
    
    echo
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    🎉 DEPLOYMENT SUCCESSFUL!                         ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo
    echo "📚 Useful Commands:"
    echo "   • View logs:           docker-compose logs -f commentator"
    echo "   • Stop services:       docker-compose down"
    echo "   • Restart:             docker-compose restart"
    echo "   • View MySQL logs:     docker-compose logs -f mysql"
    echo "   • Enter container:     docker-compose exec commentator bash"
    echo "   • Check database:      docker-compose exec mysql mysql -uroot -pProxima123# IndoorCricket"
    echo
    echo "🎵 Audio files will be saved to: ./audio/"
    echo "📝 Logs will be saved to: ./logs/"
    echo
else
    echo "❌ Services failed to start. Check logs:"
    echo "   docker-compose logs"
    exit 1
fi
