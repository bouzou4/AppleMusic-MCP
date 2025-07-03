from typing import Dict, List, Any, Optional, Union
import jwt
import asyncio
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
            },
            {
                "name": "batch_add_to_playlist",
                "description": "Add multiple songs to a playlist in a single operation. Accepts song names, IDs, or a mix. Automatically searches for songs if names provided.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "playlist_identifier": {
                            "type": "string",
                            "description": "Playlist name or ID. If name provided, will search user's playlists"
                        },
                        "songs": {
                            "type": "array",
                            "description": "List of songs to add. Each item can be a song ID, or an object with title/artist",
                            "items": {
                                "oneOf": [
                                    {"type": "string"},
                                    {
                                        "type": "object",
                                        "properties": {
                                            "title": {"type": "string"},
                                            "artist": {"type": "string"},
                                            "album": {"type": "string"}
                                        }
                                    }
                                ]
                            }
                        },
                        "create_if_missing": {
                            "type": "boolean",
                            "description": "Create playlist if it doesn't exist",
                            "default": False
                        },
                        "deduplicate": {
                            "type": "boolean", 
                            "description": "Skip songs already in playlist",
                            "default": True
                        }
                    },
                    "required": ["playlist_identifier", "songs"]
                }
            },
            {
                "name": "bulk_playlist_operations",
                "description": "Create playlists with initial songs or perform bulk operations on existing playlists",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "operations": {
                            "type": "array",
                            "description": "List of playlist operations to perform",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "operation": {
                                        "type": "string",
                                        "enum": ["create", "merge", "duplicate", "clear", "reorder"]
                                    },
                                    "playlist_name": {"type": "string"},
                                    "songs": {
                                        "type": "array",
                                        "description": "Songs for create/merge operations"
                                    },
                                    "source_playlists": {
                                        "type": "array",
                                        "description": "Source playlists for merge operations"
                                    },
                                    "order_by": {
                                        "type": "string",
                                        "enum": ["title", "artist", "date_added"],
                                        "description": "For reorder operations"
                                    }
                                }
                            }
                        },
                        "batch_mode": {
                            "type": "string",
                            "enum": ["sequential", "parallel"],
                            "default": "parallel"
                        }
                    },
                    "required": ["operations"]
                }
            },
            {
                "name": "efficient_library_search",
                "description": "Search user's library and Apple Music catalog efficiently, returning IDs optimized for other tools",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "queries": {
                            "type": "array",
                            "description": "Multiple search queries to process",
                            "items": {"type": "string"}
                        },
                        "search_scope": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["library", "catalog", "both"]
                            },
                            "default": ["both"]
                        },
                        "types": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["songs", "albums", "artists", "playlists"]
                            },
                            "default": ["songs"]
                        },
                        "return_format": {
                            "type": "string",
                            "enum": ["ids_only", "minimal", "full"],
                            "description": "Control response verbosity",
                            "default": "minimal"
                        },
                        "limit_per_query": {
                            "type": "integer",
                            "default": 10
                        }
                    },
                    "required": ["queries"]
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
                elif tool_name == "batch_add_to_playlist":
                    return await self._batch_add_to_playlist(client, arguments)
                elif tool_name == "bulk_playlist_operations":
                    return await self._bulk_playlist_operations(client, arguments)
                elif tool_name == "efficient_library_search":
                    return await self._efficient_library_search(client, arguments)
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
    
    async def _batch_add_to_playlist(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Add multiple songs to playlist with minimal API calls"""
        playlist_identifier = args["playlist_identifier"]
        songs = args["songs"]
        create_if_missing = args.get("create_if_missing", False)
        deduplicate = args.get("deduplicate", True)
        
        results = {
            "status": "success",
            "summary": {"total": len(songs), "successful": 0, "failed": 0},
            "errors": []
        }
        
        # Step 1: Resolve playlist
        playlist_id = None
        if playlist_identifier.startswith("p."):  # Apple Music library playlist ID format
            playlist_id = playlist_identifier
        else:
            # Search for playlist by name
            playlists = await client.get_library_playlists(limit=100)
            for pl in playlists.get("data", []):
                if pl["attributes"]["name"].lower() == playlist_identifier.lower():
                    playlist_id = pl["id"]
                    break
            
            if not playlist_id and create_if_missing:
                result = await client.create_playlist(playlist_identifier)
                playlist_id = result["data"][0]["id"]
        
        if not playlist_id:
            results["status"] = "error"
            results["errors"].append(f"Playlist '{playlist_identifier}' not found")
            return results
        
        # Step 2: Prepare songs for addition
        songs_to_search = []
        track_data = []
        
        for song in songs:
            if isinstance(song, str):
                # Assume it's a catalog ID
                track_data.append({"id": song, "type": "songs"})
                results["summary"]["successful"] += 1
            else:
                # Need to search for this song
                songs_to_search.append(song)
        
        # Step 3: Batch search for non-ID songs
        if songs_to_search:
            # Create efficient search queries
            for song_info in songs_to_search:
                query_parts = []
                if song_info.get("artist"):
                    query_parts.append(song_info["artist"])
                if song_info.get("title"):
                    query_parts.append(song_info["title"])
                
                if query_parts:
                    query = " ".join(query_parts)
                    search_results = await client.search_catalog(query, types="songs", limit=5)
                    
                    # Find best match
                    songs_data = search_results.get("results", {}).get("songs", {}).get("data", [])
                    if songs_data:
                        # Simple matching - take first result
                        track_data.append({"id": songs_data[0]["id"], "type": "songs"})
                        results["summary"]["successful"] += 1
                    else:
                        results["errors"].append(f"Song not found: {query}")
                        results["summary"]["failed"] += 1
        
        # Step 4: Deduplicate if requested
        if deduplicate:
            try:
                existing_tracks = await client.get_playlist_tracks(playlist_id)
                existing_ids = {t.get("attributes", {}).get("playParams", {}).get("catalogId") 
                               for t in existing_tracks if t.get("attributes", {}).get("playParams", {}).get("catalogId")}
                
                track_data = [t for t in track_data if t["id"] not in existing_ids]
            except Exception as e:
                # If deduplication fails, continue without it
                print(f"DEBUG: Deduplication failed, continuing without it: {e}")
                pass
        
        # Step 5: Add tracks to playlist
        if track_data:
            await client.add_tracks_to_playlist(playlist_id, track_data)
            results["summary"]["added"] = len(track_data)
        
        results["playlist_id"] = playlist_id
        return results

    async def _bulk_playlist_operations(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bulk playlist operations"""
        operations = args["operations"]
        batch_mode = args.get("batch_mode", "parallel")
        
        results = {
            "status": "success",
            "operations": [],
            "summary": {"total": len(operations), "successful": 0, "failed": 0}
        }
        
        # Process operations
        if batch_mode == "parallel":
            # Use asyncio.gather for parallel execution
            operation_results = await asyncio.gather(
                *[self._execute_playlist_operation(client, op) for op in operations],
                return_exceptions=True
            )
        else:
            # Sequential execution
            operation_results = []
            for op in operations:
                result = await self._execute_playlist_operation(client, op)
                operation_results.append(result)
        
        # Process results
        for i, result in enumerate(operation_results):
            if isinstance(result, Exception):
                results["operations"].append({
                    "operation": operations[i],
                    "status": "error",
                    "error": str(result)
                })
                results["summary"]["failed"] += 1
            else:
                results["operations"].append(result)
                if result["status"] == "success":
                    results["summary"]["successful"] += 1
                else:
                    results["summary"]["failed"] += 1
        
        return results

    async def _execute_playlist_operation(self, client: AppleMusicClient, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single playlist operation"""
        op_type = operation["operation"]
        
        try:
            if op_type == "create":
                # Create playlist with initial songs
                name = operation["playlist_name"]
                songs = operation.get("songs", [])
                
                # First create the playlist
                playlist_result = await client.create_playlist(name)
                playlist_id = playlist_result["data"][0]["id"]
                
                # Then add songs if provided
                if songs:
                    # Convert songs to track data using batch_add logic
                    track_data = []
                    for song in songs:
                        if isinstance(song, str):
                            track_data.append({"id": song, "type": "songs"})
                        else:
                            # Search for song
                            query_parts = []
                            if song.get("artist"):
                                query_parts.append(song["artist"])
                            if song.get("title"):
                                query_parts.append(song["title"])
                            
                            if query_parts:
                                query = " ".join(query_parts)
                                search_results = await client.search_catalog(query, types="songs", limit=1)
                                songs_data = search_results.get("results", {}).get("songs", {}).get("data", [])
                                if songs_data:
                                    track_data.append({"id": songs_data[0]["id"], "type": "songs"})
                    
                    if track_data:
                        await client.add_tracks_to_playlist(playlist_id, track_data)
                
                return {"status": "success", "operation": op_type, "playlist_id": playlist_id, "songs_added": len(track_data) if songs else 0}
                
            elif op_type == "clear":
                # Clear all tracks from playlist
                playlist_name = operation["playlist_name"]
                
                # Find playlist ID by name
                playlists = await client.get_library_playlists(limit=100)
                playlist_id = None
                for pl in playlists.get("data", []):
                    if pl["attributes"]["name"].lower() == playlist_name.lower():
                        playlist_id = pl["id"]
                        break
                
                if not playlist_id:
                    return {"status": "error", "operation": op_type, "error": f"Playlist '{playlist_name}' not found"}
                
                # Get all tracks and delete them
                tracks = await client.get_playlist_tracks(playlist_id)
                if tracks:
                    track_indices = list(range(len(tracks)))
                    await client.delete_playlist_tracks(playlist_id, track_indices)
                
                return {"status": "success", "operation": op_type, "playlist_id": playlist_id, "tracks_removed": len(tracks)}
                
            else:
                return {"status": "error", "operation": op_type, "error": f"Operation '{op_type}' not yet implemented"}
                
        except Exception as e:
            return {"status": "error", "operation": op_type, "error": str(e)}

    async def _efficient_library_search(self, client: AppleMusicClient, args: Dict[str, Any]) -> Dict[str, Any]:
        """Efficient multi-query search"""
        queries = args["queries"]
        search_scope = args.get("search_scope", ["both"])
        types = args.get("types", ["songs"])
        return_format = args.get("return_format", "minimal")
        limit = args.get("limit_per_query", 10)
        
        results = {
            "status": "success",
            "queries": {},
            "summary": {"total_queries": len(queries), "total_results": 0}
        }
        
        for query in queries:
            query_results = {"library": [], "catalog": []}
            
            # Execute searches based on scope
            search_tasks = []
            
            if "library" in search_scope or "both" in search_scope:
                for type_name in types:
                    search_tasks.append(("library", type_name, 
                        client.search_library(query, types=f"library-{type_name}", limit=limit)))
            
            if "catalog" in search_scope or "both" in search_scope:
                for type_name in types:
                    search_tasks.append(("catalog", type_name,
                        client.search_catalog(query, types=type_name, limit=limit)))
            
            # Execute all searches for this query in parallel
            search_results = await asyncio.gather(*[task[2] for task in search_tasks], return_exceptions=True)
            
            # Process results based on return_format
            for i, result in enumerate(search_results):
                if isinstance(result, Exception):
                    continue
                    
                scope, type_name = search_tasks[i][0], search_tasks[i][1]
                
                if return_format == "ids_only":
                    # Extract just IDs
                    items = result.get("results", {}).get(type_name, {}).get("data", [])
                    ids = [item["id"] for item in items]
                    query_results[scope].extend(ids)
                    
                elif return_format == "minimal":
                    # Extract ID, name, and key attributes
                    items = result.get("results", {}).get(type_name, {}).get("data", [])
                    minimal_items = []
                    
                    for item in items:
                        attrs = item.get("attributes", {})
                        minimal_item = {
                            "id": item["id"],
                            "name": attrs.get("name"),
                            "type": type_name
                        }
                        
                        # Add type-specific attributes
                        if type_name == "songs":
                            minimal_item["artist"] = attrs.get("artistName")
                            minimal_item["catalog_id"] = attrs.get("playParams", {}).get("catalogId")
                            minimal_item["isrc"] = attrs.get("isrc")
                        
                        minimal_items.append(minimal_item)
                        
                    query_results[scope].extend(minimal_items)
                    
                else:  # full
                    items = result.get("results", {}).get(type_name, {}).get("data", [])
                    query_results[scope].extend(items)
            
            results["queries"][query] = query_results
            results["summary"]["total_results"] += len(query_results["library"]) + len(query_results["catalog"])
        
        return results