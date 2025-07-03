import httpx
from typing import Dict, List, Optional, Any
import asyncio
from datetime import datetime, timedelta

from app.core.config import settings
from app.core.security import generate_developer_token, validate_developer_token

class AppleMusicClient:
    """Apple Music API client with authentication and rate limiting"""
    
    BASE_URL = "https://api.music.apple.com/v1"
    
    def __init__(self):
        self.developer_token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        self.user_token: Optional[str] = None
        self.client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
            self.client = None
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authentication"""
        headers = {
            "Authorization": f"Bearer {self.developer_token}",
            "Content-Type": "application/json"
        }
        
        if self.user_token:
            headers["Music-User-Token"] = self.user_token
            
        return headers
    
    async def ensure_developer_token(self):
        """Ensure we have a valid developer token"""
        if not self.developer_token or not validate_developer_token(self.developer_token):
            self.developer_token = generate_developer_token()
            self.token_expires = datetime.utcnow() + timedelta(hours=12)
    
    def set_user_token(self, user_token: str):
        """Set user token for authenticated requests"""
        self.user_token = user_token
    
    async def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to Apple Music API"""
        await self.ensure_developer_token()
        
        url = f"{self.BASE_URL}{endpoint}"
        headers = self._get_headers()
        
        response = await self.client.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data
        )
        
        if response.status_code == 429:  # Rate limited
            retry_after = int(response.headers.get("Retry-After", 60))
            await asyncio.sleep(retry_after)
            return await self._make_request(method, endpoint, params, json_data)
        
        response.raise_for_status()
        
        # Handle empty responses
        if response.content:
            try:
                return response.json()
            except ValueError as e:
                print(f"DEBUG: Failed to parse JSON response: {e}")
                print(f"DEBUG: Response content: {response.text}")
                raise
        else:
            # Return empty dict for successful requests with no content
            return {}
    
    # Catalog Search (for finding song IDs)
    async def search_catalog(
        self, 
        query: str, 
        types: str = "songs",
        limit: int = 25,
        country: str = "US"
    ) -> Dict[str, Any]:
        """Search Apple Music catalog for songs, albums, artists"""
        params = {
            "term": query,
            "types": types,
            "limit": limit
        }
        return await self._make_request("GET", f"/catalog/{country}/search", params=params)
    
    async def search_songs(self, query: str, limit: int = 10, country: str = "US") -> List[Dict[str, Any]]:
        """Search for songs and return simplified track list for LLM usage"""
        print(f"DEBUG: AppleMusicClient.search_songs called with query='{query}', limit={limit}")
        
        try:
            search_results = await self.search_catalog(query, types="songs", limit=limit, country=country)
            print(f"DEBUG: search_catalog returned: {type(search_results)}")
        except Exception as e:
            print(f"ERROR: search_catalog failed - {type(e).__name__}: {e}")
            raise
        
        songs = search_results.get("results", {}).get("songs", {}).get("data", [])
        
        # Return simplified format
        return [
            {
                "id": song["id"],
                "title": song["attributes"]["name"],
                "artist": song["attributes"]["artistName"],
                "album": song["attributes"].get("albumName", ""),
                "duration_ms": song["attributes"].get("durationInMillis", 0),
                "release_date": song["attributes"].get("releaseDate", ""),
                "preview_url": song["attributes"].get("previews", [{}])[0].get("url", "") if song["attributes"].get("previews") else ""
            }
            for song in songs
        ]
    
    # Library Read Operations
    async def get_library_songs(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get user's library songs"""
        params = {"limit": limit, "offset": offset}
        return await self._make_request("GET", "/me/library/songs", params=params)
    
    async def get_library_playlists(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get user's library playlists"""
        params = {"limit": limit, "offset": offset}
        return await self._make_request("GET", "/me/library/playlists", params=params)
    
    async def get_library_albums(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get user's library albums"""
        params = {"limit": limit, "offset": offset}
        return await self._make_request("GET", "/me/library/albums", params=params)
    
    async def get_library_artists(self, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        """Get user's library artists"""
        params = {"limit": limit, "offset": offset}
        return await self._make_request("GET", "/me/library/artists", params=params)
    
    async def get_recently_played(self, limit: int = 10) -> Dict[str, Any]:
        """Get recently played tracks"""
        params = {"limit": limit}
        return await self._make_request("GET", "/me/recent/played/tracks", params=params)
    
    async def search_library(
        self, 
        query: str, 
        types: str = "library-songs",
        limit: int = 25
    ) -> Dict[str, Any]:
        """Search user's library"""
        params = {
            "term": query,
            "types": types,
            "limit": limit
        }
        return await self._make_request("GET", "/me/library/search", params=params)
    
    # Library Write Operations
    async def rate_song(self, song_id: str, rating: int) -> Dict[str, Any]:
        """Rate a song (1-5 stars, converted to 0-100 for API)"""
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        # Convert 1-5 star rating to 0-100 API format
        api_rating = (rating - 1) * 25  # 1->0, 2->25, 3->50, 4->75, 5->100
        
        json_data = {"attributes": {"value": api_rating}}
        return await self._make_request("PUT", f"/me/ratings/songs/{song_id}", json_data=json_data)
    
    async def create_playlist(
        self, 
        name: str, 
        description: Optional[str] = None,
        track_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a new playlist"""
        json_data = {
            "attributes": {
                "name": name,
                "description": description or ""
            }
        }
        
        if track_ids:
            json_data["relationships"] = {
                "tracks": {
                    "data": [{"id": track_id, "type": "library-songs"} for track_id in track_ids]
                }
            }
        
        return await self._make_request("POST", "/me/library/playlists", json_data=json_data)
    
    async def add_to_library(self, song_ids: List[str]) -> Dict[str, Any]:
        """Add songs to library by catalog IDs"""
        json_data = {
            "data": [{"id": song_id, "type": "songs"} for song_id in song_ids]
        }
        return await self._make_request("POST", "/me/library", json_data=json_data)
    
    # Batch Operations Methods
    async def get_playlist_tracks(self, playlist_id: str, limit: int = 300) -> List[Dict[str, Any]]:
        """Get all tracks from a playlist with pagination"""
        all_tracks = []
        offset = 0
        
        try:
            while True:
                response = await self._make_request(
                    "GET", 
                    f"/me/library/playlists/{playlist_id}/tracks",
                    params={"limit": limit, "offset": offset}
                )
                
                tracks = response.get("data", [])
                all_tracks.extend(tracks)
                
                # Check for next page
                if not response.get("next") or len(tracks) < limit:
                    break
                offset += limit
        except Exception as e:
            # If playlist is empty or newly created, return empty list
            print(f"DEBUG: get_playlist_tracks failed for {playlist_id}: {e}")
            return []
        
        return all_tracks

    async def add_tracks_to_playlist(self, playlist_id: str, track_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """Add tracks to playlist. track_data should have 'id' and 'type' for each track"""
        # Apple Music API limits to 100 tracks per request
        for i in range(0, len(track_data), 100):
            batch = track_data[i:i+100]
            json_data = {"data": batch}
            
            await self._make_request(
                "POST",
                f"/me/library/playlists/{playlist_id}/tracks",
                json_data=json_data
            )
        
        return {"added": len(track_data)}

    async def delete_playlist_tracks(self, playlist_id: str, track_indices: List[int]) -> Dict[str, Any]:
        """Delete tracks from playlist by their indices"""
        # Apple Music uses track indices for deletion
        json_data = {"data": [{"id": str(idx), "type": "library-playlist-tracks"} for idx in track_indices]}
        
        return await self._make_request(
            "DELETE",
            f"/me/library/playlists/{playlist_id}/tracks",
            json_data=json_data
        )

    async def update_playlist_tracks(self, playlist_id: str, track_data: List[Dict[str, str]]) -> Dict[str, Any]:
        """Replace all tracks in a playlist (for reordering)"""
        json_data = {"data": track_data}
        
        return await self._make_request(
            "PUT",
            f"/me/library/playlists/{playlist_id}/tracks",
            json_data=json_data
        )

    async def parallel_search(self, queries: List[str], search_type: str, types: str, limit: int) -> List[Dict[str, Any]]:
        """Execute multiple searches in parallel"""
        if search_type == "catalog":
            search_tasks = [self.search_catalog(q, types=types, limit=limit) for q in queries]
        else:  # library
            search_tasks = [self.search_library(q, types=f"library-{types}", limit=limit) for q in queries]
        
        results = await asyncio.gather(*search_tasks, return_exceptions=True)
        return results

    async def get_artist_top_songs(self, artist_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top songs for an artist"""
        # Note: Apple Music doesn't have direct "top songs" relationship in the API
        # We'll search for the artist and get their songs
        response = await self._make_request(
            "GET",
            f"/catalog/us/artists/{artist_id}/songs",
            params={"limit": limit}
        )
        return response.get("data", [])

    async def get_charts(self, types: str = "songs", genre: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """Get music charts, optionally filtered by genre"""
        params = {"types": types, "limit": limit}
        if genre:
            params["genre"] = genre
        
        return await self._make_request("GET", "/catalog/us/charts", params=params)