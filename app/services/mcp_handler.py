from typing import Dict, List, Any, Optional
import jwt
from app.services.apple_music import AppleMusicClient
from app.core.config import settings
from app.core.security import decrypt_token

class MCPHandler:
    """Handle MCP protocol requests and route to Apple Music API"""
    
    def __init__(self):
        self.apple_client = AppleMusicClient()
    
    def _extract_user_token(self, authorization_header: Optional[str]) -> Optional[str]:
        """Extract MusicKit user token from OAuth Bearer token"""
        if not authorization_header or not authorization_header.startswith("Bearer "):
            return None
        
        try:
            access_token = authorization_header[7:]  # Remove "Bearer " prefix
            payload = jwt.decode(
                access_token, 
                settings.jwt_secret_key, 
                algorithms=["HS256"]
            )
            
            encrypted_user_token = payload.get("apple_user_token")
            if encrypted_user_token:
                return decrypt_token(encrypted_user_token)
            
        except (jwt.InvalidTokenError, Exception) as e:
            print(f"DEBUG: Failed to extract user token: {e}")
        
        return None
    
    async def get_tools(self) -> List[Dict[str, Any]]:
        """Return available MCP tools"""
        return [
            {
                "name": "search_songs",
                "description": "Search Apple Music catalog for songs",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query (artist, song title, etc.)"},
                        "limit": {"type": "number", "default": 10, "description": "Number of results to return"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_library_stats",
                "description": "Get statistics about the user's music library",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_recently_played", 
                "description": "Get recently played tracks",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "number", "default": 10}
                    }
                }
            },
            {
                "name": "search_library",
                "description": "Search the user's music library",
                "inputSchema": {
                    "type": "object", 
                    "properties": {
                        "query": {"type": "string"},
                        "types": {"type": "string", "default": "library-songs"},
                        "limit": {"type": "number", "default": 25}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "rate_song",
                "description": "Rate a song from 1-5 stars", 
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "song_id": {"type": "string", "description": "Apple Music song ID"},
                        "rating": {"type": "number", "minimum": 1, "maximum": 5}
                    },
                    "required": ["song_id", "rating"]
                }
            },
            {
                "name": "create_playlist",
                "description": "Create a new playlist",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "track_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["name"]
                }
            },
            {
                "name": "add_to_library",
                "description": "Add songs to library",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "song_ids": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["song_ids"]
                }
            }
        ]
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any], authorization_header: Optional[str] = None) -> Dict[str, Any]:
        """Handle MCP tool calls"""
        print(f"DEBUG: MCPHandler.handle_tool_call - tool: {tool_name}, args: {arguments}")
        
        # Extract user token from OAuth access token if provided
        user_token = self._extract_user_token(authorization_header)
        
        apple_client = AppleMusicClient()
        if user_token:
            print(f"DEBUG: Extracted user token from OAuth access token")
            apple_client.user_token = user_token
        else:
            print(f"DEBUG: No user token found, using catalog-only access")
        
        try:
            async with apple_client as client:
                print(f"DEBUG: Apple Music client context established")
                if tool_name == "search_songs":
                    return await self._search_songs(client, arguments)
                elif tool_name == "get_library_stats":
                    return await self._get_library_stats(client, arguments)
                elif tool_name == "get_recently_played":
                    return await self._get_recently_played(client, arguments)
                elif tool_name == "search_library":
                    return await self._search_library(client, arguments)
                elif tool_name == "rate_song":
                    return await self._rate_song(client, arguments)
                elif tool_name == "create_playlist":
                    return await self._create_playlist(client, arguments)
                elif tool_name == "add_to_library":
                    return await self._add_to_library(client, arguments)
                else:
                    raise ValueError(f"Unknown tool: {tool_name}")
        except Exception as e:
            print(f"ERROR: MCPHandler.handle_tool_call failed - {type(e).__name__}: {e}")
            import traceback
            print(f"ERROR: Full traceback:\n{traceback.format_exc()}")
            raise
    
    async def _search_songs(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search Apple Music catalog for songs"""
        # Debug: log what we received
        print(f"DEBUG: search_songs received args: {args}")
        
        if "query" not in args:
            raise ValueError(f"Missing required 'query' parameter. Received args: {args}")
        
        query = args["query"]
        limit = args.get("limit", 10)
        
        songs = await client.search_songs(query, limit=limit)
        return {"songs": songs}
    
    async def _get_library_stats(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get library statistics"""
        # Get basic counts from library endpoints
        songs = await client.get_library_songs(limit=1)
        playlists = await client.get_library_playlists(limit=1)
        albums = await client.get_library_albums(limit=1)
        artists = await client.get_library_artists(limit=1)
        
        # Extract totals from meta information
        total_songs = songs.get("meta", {}).get("total", 0)
        total_playlists = playlists.get("meta", {}).get("total", 0)
        total_albums = albums.get("meta", {}).get("total", 0)
        total_artists = artists.get("meta", {}).get("total", 0)
        
        return {
            "total_songs": total_songs,
            "total_playlists": total_playlists,
            "total_albums": total_albums,
            "total_artists": total_artists
        }
    
    async def _get_recently_played(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get recently played tracks"""
        limit = args.get("limit", 10)
        return await client.get_recently_played(limit=limit)
    
    async def _search_library(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Search user's library"""
        query = args["query"]
        types = args.get("types", "library-songs")
        limit = args.get("limit", 25)
        
        return await client.search_library(query, types=types, limit=limit)
    
    async def _rate_song(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Rate a song"""
        song_id = args["song_id"]
        rating = args["rating"]
        
        result = await client.rate_song(song_id, rating)
        return {"status": "success", "rating": rating, "song_id": song_id}
    
    async def _create_playlist(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new playlist"""
        name = args["name"]
        description = args.get("description")
        track_ids = args.get("track_ids", [])
        
        result = await client.create_playlist(name, description, track_ids)
        return {"status": "success", "playlist": result}
    
    async def _add_to_library(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add songs to library"""
        song_ids = args["song_ids"]
        
        result = await client.add_to_library(song_ids)
        return {"status": "success", "added_songs": len(song_ids)}