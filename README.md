# Apple Music MCP Server

A Model Context Protocol (MCP) server that provides LLMs with comprehensive access to Apple Music libraries.

## Overview

This server enables MCP-compatible LLMs to read and write Apple Music library data including:
- **Search songs** - Find tracks in Apple Music catalog
- **Library management** - View library statistics and content
- **Recently played** - Access listening history
- **Song ratings** - Rate tracks (1-5 stars)
- **Playlist creation** - Create and manage playlists
- **Add to library** - Add songs from catalog to user library

## Architecture

- **Runtime**: Python 3.11+ with FastAPI
- **Authentication**: JWT tokens for Apple Music API
- **Deployment**: Docker containers
- **Direct API**: No local database - queries Apple Music directly

## MCP Tools Available

- `search_songs` - Search Apple Music catalog for tracks
- `get_library_stats` - Get user's library statistics
- `get_recently_played` - Fetch recently played tracks
- `search_library` - Search within user's library
- `rate_song` - Rate a song (1-5 stars)
- `create_playlist` - Create new playlists
- `add_to_library` - Add songs to user's library

## Quick Start

### Prerequisites
- Apple Developer account with MusicKit enabled
- Apple Music subscription
- Docker

### Setup

1. **Clone and configure**
   ```bash
   git clone <repository-url>
   cd apple-music-mcp
   
   # Copy environment template
   cp .env.example .env
   ```

2. **Add Apple Music credentials to `.env`**
   ```bash
   APPLE_TEAM_ID=your_team_id_here
   APPLE_KEY_ID=your_key_id_here
   APPLE_PRIVATE_KEY_PATH=/keys/AuthKey.p8
   ```

3. **Place your Apple Music private key**
   ```bash
   mkdir -p docker/keys
   # Copy your AuthKey_XXXXXXXXXX.p8 file to docker/keys/AuthKey.p8
   ```

### Running

**Using Docker:**
```bash
# Build image
docker build -f docker/Dockerfile -t apple-music-mcp .

# Run container
docker run --rm -p 8080:8080 --env-file .env \
  -v $(pwd)/docker/keys:/keys:ro apple-music-mcp
```

**Using Docker Compose:**
```bash
# From docker directory
cd docker
docker-compose up -d
```

### Verify Installation
```bash
# Check health
curl http://localhost:8080/health

# Expected response:
# {"status":"healthy","timestamp":"...","version":"1.0.0","services":{"server":"online"}}
```

## API Endpoints

### Core Endpoints
- `GET /` - Server info
- `GET /health` - Health check

### Apple Music Integration
The server exposes MCP tools rather than direct REST endpoints. Tools are called through the MCP protocol by compatible LLM clients.

## MCP Integration

Configure your MCP-compatible LLM client to connect to `http://localhost:8080` for Apple Music functionality.

Example tool usage:
- Search for songs: `search_songs(query="Taylor Swift Love Story")`
- Get library stats: `get_library_stats()`
- Rate a song: `rate_song(song_id="123456789", rating=5)`

## Status

✅ **Basic functionality implemented**
- FastAPI server with health checks
- Apple Music API client with JWT authentication
- MCP tool definitions for all major operations
- Docker deployment ready

🚧 **TODO for full functionality:**
- User token authentication flow
- Error handling and validation
- Rate limiting implementation

## Security

- JWT token authentication with Apple Music API
- Non-root Docker container execution
- Environment-based configuration
- Read-only key volume mounts