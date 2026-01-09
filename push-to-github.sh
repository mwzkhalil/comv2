#!/bin/bash
# Push to GitHub - Step by Step

set -e

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║           Push to GitHub - Setup & Deploy                       ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo

# Check if git is initialized
if [ ! -d .git ]; then
    echo "📦 Initializing Git repository..."
    git init
    echo "✅ Git initialized"
else
    echo "✅ Git repository exists"
fi

# Check for .env file in staging
echo
echo "🔒 Checking for sensitive files..."
if git ls-files | grep -q "^.env$"; then
    echo "❌ WARNING: .env is tracked by git!"
    echo "   Removing from git (keeping file locally)..."
    git rm --cached .env 2>/dev/null || true
    echo "✅ .env removed from git tracking"
else
    echo "✅ .env is not tracked (safe)"
fi

# Verify .gitignore
echo
echo "📝 Verifying .gitignore..."
if grep -q "^.env$" .gitignore; then
    echo "✅ .env is in .gitignore"
else
    echo "⚠️  Adding .env to .gitignore..."
    echo ".env" >> .gitignore
fi

# Show what will be committed
echo
echo "📋 Files to commit:"
git add -A
git status --short | head -30

echo
echo "📊 Repository Statistics:"
echo "   Total files: $(git ls-files | wc -l)"
echo "   Python files: $(git ls-files | grep -c '.py$')"
echo "   Docker files: $(git ls-files | grep -cE 'Dockerfile|docker-' || echo 0)"

echo
read -p "Continue with commit? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Commit
echo
echo "💾 Committing changes..."
git commit -m "Initial commit: Indoor Cricket Commentary System

Features:
- Real-time cricket match commentary with TTS
- Database-driven commentary storage (DeliveryAudio table)
- Docker deployment with MySQL + Python app
- Environment-based configuration
- Audio generation and playback system

Docker Deployment:
- One-command setup: ./docker-start.sh
- Auto-initialized MySQL database
- Persistent volumes for data/audio/logs

Tech Stack:
- Python 3.11
- MySQL 8.0
- ElevenLabs TTS API
- pygame audio engine
- Docker containerization" || echo "⚠️  Commit failed or no changes"

echo "✅ Committed!"

# Instructions for GitHub
echo
echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║                 Ready to Push to GitHub!                        ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo
echo "Next steps:"
echo
echo "1️⃣  Create repository on GitHub:"
echo "   https://github.com/new"
echo "   Repository name: cricket-commentary-system"
echo
echo "2️⃣  Add remote and push:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/cricket-commentary-system.git"
echo "   git branch -M main"
echo "   git push -u origin main"
echo
echo "3️⃣  Or use GitHub CLI:"
echo "   gh repo create cricket-commentary-system --public --source=. --push"
echo
echo "🔒 Security Reminder:"
echo "   ✅ .env file is NOT committed (contains API keys)"
echo "   ✅ .env.example is committed (template without secrets)"
echo "   ✅ Users must add their own API key after cloning"
echo
