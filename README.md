# Apple Music MCP Server

A Model Context Protocol (MCP) server that provides LLMs with comprehensive access to Apple Music libraries through OAuth 2.1 + MusicKit authentication.

## Overview

This server enables MCP-compatible LLMs to read and write Apple Music library data including:
- **Search songs** - Find tracks in Apple Music catalog
- **Library management** - View library statistics and content
- **Recently played** - Access listening history
- **Song ratings** - Rate tracks (1-5 stars)
- **Playlist creation** - Create and manage playlists
- **Add to library** - Add songs from catalog to user library
- **Batch operations** - Efficient bulk playlist and search operations

## Architecture

- **Runtime**: Python 3.11+ with FastAPI
- **Authentication**: OAuth 2.1 + MusicKit hybrid authentication
- **Database**: SQLite for OAuth state management
- **Deployment**: Docker containers
- **Direct API**: Queries Apple Music API directly (no music data caching)

## MCP Tools Available

### Core Tools
- `search_songs` - Search Apple Music catalog for tracks
- `get_library_stats` - Get user's library statistics
- `get_recently_played` - Fetch recently played tracks
- `search_library` - Search within user's library
- `rate_song` - Rate a song (1-5 stars)
- `create_playlist` - Create new playlists
- `add_to_library` - Add songs to user's library

### Batch Operations
- `batch_add_to_playlist` - Add multiple songs to a playlist efficiently
- `bulk_playlist_operations` - Perform multiple playlist operations in parallel
- `efficient_library_search` - Search multiple queries simultaneously with optimized output formats

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
   # Apple Music API
   APPLE_TEAM_ID=your_team_id_here
   APPLE_KEY_ID=your_key_id_here
   APPLE_PRIVATE_KEY_PATH=/keys/AuthKey.p8
   
   # OAuth Configuration
   OAUTH_BASE_URL=http://localhost:3600
   JWT_SECRET_KEY=your_strong_random_secret_key
   TOKEN_ENCRYPTION_KEY=your_fernet_encryption_key
   ```

3. **Place your Apple Music private key**
   ```bash
   mkdir -p docker/keys
   # Copy your AuthKey_XXXXXXXXXX.p8 file to docker/keys/AuthKey.p8
   ```

### Running

**Using Docker Compose (Recommended):**
```bash
# From docker directory
cd docker
docker-compose up -d
```

**Using Docker:**
```bash
# Build image
docker build -f docker/Dockerfile -t apple-music-mcp .

# Run container
docker run --rm -p 3600:3600 --env-file .env \
  -v $(pwd)/docker/keys:/keys:ro apple-music-mcp
```

### Verify Installation
```bash
# Check health
curl http://localhost:3600/health

# Expected response:
# {"status":"healthy","timestamp":"...","version":"1.0.0","services":{"server":"online"}}
```

## Authentication Flow

### OAuth 2.1 + MusicKit Hybrid
1. **Client Registration**: MCP clients dynamically register via `/oauth/register`
2. **Authorization**: Client redirects to `/oauth/authorize`
3. **MusicKit Authentication**: User authenticates through Apple's MusicKit web interface
4. **Token Exchange**: Client exchanges authorization code for access token at `/oauth/token`
5. **MCP Access**: Client uses Bearer token for authenticated MCP tool calls

### Available Endpoints
- `GET /.well-known/oauth-authorization-server` - OAuth server metadata
- `POST /oauth/register` - Dynamic client registration
- `GET /oauth/authorize` - Authorization endpoint  
- `POST /oauth/token` - Token exchange
- `GET /mcp` - MCP server info
- `POST /mcp` - MCP tool calls
- `GET /health` - Health check

## MCP Integration

### Integration
1. Add custom integration in your LLM platform (e.g., Anthropic Claude)
2. Use server URL: `http://localhost:3600` (or your deployed URL)
3. Complete OAuth flow when prompted
4. Access Apple Music tools through Claude conversations

### Example Usage
```
User: "Search for songs by Daft Punk"
Claude: Uses search_songs tool → Returns Apple Music catalog results

User: "What's in my music library?"  
Claude: Uses get_library_stats tool → Returns library statistics

User: "Rate this song 5 stars"
Claude: Uses rate_song tool → Updates song rating in Apple Music

User: "Add these 20 songs to my workout playlist"
Claude: Uses batch_add_to_playlist  → Performs efficiently in parallel
```

## Batch Operations Features

### Performance Optimizations
- **Parallel Processing**: Multiple operations execute simultaneously using asyncio.gather()
- **Reduced API Calls**: Batch requests minimize round trips to Apple Music API
- **Smart Deduplication**: Automatically prevents adding duplicate tracks to playlists
- **Mixed Input Support**: Handle both Apple Music IDs and artist/title search objects
- **Configurable Output Formats**: Choose between ids_only, minimal, or full response formats

### batch_add_to_playlist
Efficiently add multiple songs to a playlist with automatic song resolution:
```python
{
  "playlist_identifier": "My Workout Playlist",  # Name or ID
  "songs": [
    "1468058171",  # Apple Music ID
    {"title": "Blinding Lights", "artist": "The Weeknd"},  # Search object
    {"title": "Watermelon Sugar", "artist": "Harry Styles"}
  ],
  "create_if_missing": true,  # Create playlist if it doesn't exist
  "deduplicate": true  # Skip songs already in playlist
}
```

### bulk_playlist_operations
Perform multiple playlist operations in parallel:
```python
{
  "operations": [
    {
      "operation": "create",
      "playlist_name": "New Playlist 1",
      "songs": ["1468058171", "1193701400"]
    },
    {
      "operation": "create", 
      "playlist_name": "New Playlist 2"
    },
    {
      "operation": "clear",
      "playlist_name": "Old Playlist"
    }
  ],
  "batch_mode": "parallel"  # or "sequential"
}
```

### efficient_library_search
Search multiple queries simultaneously with optimized responses:
```python
{
  "queries": ["Taylor Swift", "Ed Sheeran", "Billie Eilish"],
  "search_scope": ["catalog"],  # "library", "catalog", or "both"
  "types": ["songs"],  # "songs", "albums", "artists", "playlists"
  "return_format": "minimal",  # "ids_only", "minimal", or "full"
  "limit_per_query": 5
}
```

## Status

✅ **Production Ready**
- ✅ FastAPI server with health checks
- ✅ Apple Music API client with JWT authentication  
- ✅ OAuth 2.1 server with dynamic client registration
- ✅ MusicKit authentication integration
- ✅ All 10 MCP tools implemented and tested (7 core + 3 batch operations)
- ✅ Authorization header extraction and user token handling
- ✅ Docker deployment with environment configuration
- ✅ HTTP client lifecycle management

🎯 **Core Features Working**
- Catalog search operations (no auth required)
- OAuth 2.1 authentication flow end-to-end
- MusicKit user authentication via web interface  
- Bearer token extraction for authenticated operations
- Library operations (requires user authentication)
- Batch operations with parallel processing and optimized API usage

## Security

- ✅ OAuth 2.1 with PKCE for secure authentication
- ✅ JWT token authentication with Apple Music API
- ✅ MusicKit user token encryption at rest
- ✅ Non-root Docker container execution
- ✅ Environment-based configuration
- ✅ Read-only key volume mounts
- ✅ CORS configuration for web integration