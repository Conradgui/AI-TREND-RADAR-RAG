#!/bin/bash

# AI Trend Radar RAG - Unified Setup Script
# This script sets up the complete local environment

set -e

echo "🚀 AI Trend Radar RAG - Unified Setup"
echo "======================================"

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi
echo "✅ Python 3 found: $(python3 --version)"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is required but not installed."
    exit 1
fi
echo "✅ Node.js found: $(node --version)"

# Check pnpm
if ! command -v pnpm &> /dev/null; then
    echo "⚠️  pnpm not found, installing..."
    npm install -g pnpm
fi
echo "✅ pnpm found: $(pnpm --version)"

# Check Docker (optional)
if command -v docker &> /dev/null; then
    echo "✅ Docker found: $(docker --version)"
    DOCKER_AVAILABLE=true
else
    echo "⚠️  Docker not found (optional, Neo4j will not be available)"
    DOCKER_AVAILABLE=false
fi

# Setup configuration
echo ""
echo "⚙️  Setting up configuration..."

if [ ! -f .env ]; then
    if [ -f .env.unified.example ]; then
        cp .env.unified.example .env
        echo "✅ Created .env from .env.unified.example"
        echo "📝 Please edit .env and add your API keys"
    elif [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env from .env.example"
        echo "📝 Please edit .env and add your API keys"
    else
        echo "❌ No .env.example found"
        exit 1
    fi
else
    echo "✅ .env already exists"
fi

# Setup Python environment
echo ""
echo "🐍 Setting up Python environment..."

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✅ Created Python virtual environment"
fi

echo "📦 Installing Python dependencies..."
.venv/bin/pip install -r rag/requirements.txt
echo "✅ Python dependencies installed"

# Setup Node.js environment
echo ""
echo "📦 Setting up Node.js environment..."
pnpm install
echo "✅ Node.js dependencies installed"

# Setup Neo4j (if Docker available)
if [ "$DOCKER_AVAILABLE" = true ]; then
    echo ""
    echo "🐘 Setting up Neo4j..."
    if docker ps | grep -q neo4j; then
        echo "✅ Neo4j already running"
    else
        echo "🚀 Starting Neo4j..."
        docker-compose up -d neo4j
        echo "✅ Neo4j started"
        echo "⏳ Waiting for Neo4j to be ready..."
        sleep 10
    fi
fi

# Run data pipeline
echo ""
echo "📊 Running data pipeline..."
pnpm start
echo "✅ Data pipeline completed"

# Generate manifest
echo ""
echo "📋 Generating manifest..."
pnpm manifest
echo "✅ Manifest generated"

# Run RAG ingestion
echo ""
echo "🔍 Running RAG ingestion..."
.venv/bin/python -m rag.ingest
echo "✅ RAG ingestion completed"

# Run tests
echo ""
echo "🧪 Running tests..."
.venv/bin/python -m pytest rag/tests/ -v --tb=short || echo "⚠️  Some tests failed"
echo "✅ Tests completed"

# Start services
echo ""
echo "🚀 Starting services..."
echo ""
echo "To start the RAG server, run:"
echo "  .venv/bin/python -m rag.server"
echo ""
echo "To start the data pipeline watcher, run:"
echo "  pnpm start:watch"
echo ""
echo "📊 Dashboard will be available at: http://localhost:8001"
echo ""
echo "✅ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "  1. Edit .env and add your API keys"
echo "  2. Start the RAG server: .venv/bin/python -m rag.server"
echo "  3. Open http://localhost:8001 in your browser"
