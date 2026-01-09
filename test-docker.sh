#!/bin/bash
# Test Docker deployment

set -e

echo "🧪 Testing Docker Deployment"
echo "============================"
echo

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker not installed"
    exit 1
fi
echo "✅ Docker installed: $(docker --version)"

# Check Docker Compose
if command -v docker-compose &> /dev/null; then
    echo "✅ Docker Compose installed: $(docker-compose --version)"
elif docker compose version &> /dev/null; then
    echo "✅ Docker Compose (plugin) installed: $(docker compose version)"
else
    echo "❌ Docker Compose not installed"
    exit 1
fi

# Check files
echo
echo "📁 Checking files..."
files=("Dockerfile" "docker-compose.yml" "docker-init.sql" "requirements.txt" ".env.example")
for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ Missing: $file"
        exit 1
    fi
done

# Check .env
echo
if [ -f .env ]; then
    echo "✅ .env file exists"
    if grep -q "ELEVENLABS_API_KEY=sk_" .env; then
        echo "   ✅ API key is set"
    else
        echo "   ⚠️  API key not set (will use placeholder)"
    fi
else
    echo "⚠️  No .env file (will use .env.example)"
fi

# Test build (dry run)
echo
echo "🏗️  Testing Docker configuration..."
if docker compose config > /dev/null 2>&1; then
    echo "✅ docker-compose.yml is valid"
elif docker-compose config > /dev/null 2>&1; then
    echo "✅ docker-compose.yml is valid"
else
    echo "❌ docker-compose.yml has errors"
    docker compose config 2>&1 || docker-compose config 2>&1
    exit 1
fi

# Show configuration
echo
echo "📊 Docker Services:"
if command -v docker-compose &> /dev/null; then
    docker-compose config --services
else
    docker compose config --services
fi

echo
echo "╔══════════════════════════════════════════════════════════╗"
echo "║           ✅ DOCKER SETUP IS VALID!                     ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo
echo "Ready to deploy! Run:"
echo "   ./docker-start.sh"
echo
echo "Or manually:"
echo "   docker-compose build"
echo "   docker-compose up -d"
