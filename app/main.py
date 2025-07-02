from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from datetime import datetime
import uvicorn
import json
import asyncio
from typing import Dict, Any, Optional, Union, AsyncIterator
from pydantic import BaseModel

from app.core.config import settings
from app.services.mcp_handler import MCPHandler

app = FastAPI(
    title="Apple Music MCP Server",
    description="Model Context Protocol server for Apple Music integration",
    version="1.0.0",
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize MCP handler
mcp_handler = MCPHandler()

# Pydantic models for MCP requests
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "Apple Music MCP Server", "version": "1.0.0"}

@app.post("/mcp")
@app.get("/mcp")
async def mcp_endpoint(request: Request, mcp_request: Optional[MCPRequest] = None):
    """
    Streamable HTTP MCP endpoint
    Handles both GET (for SSE upgrade) and POST (for JSON-RPC) requests
    """
    if request.method == "GET":
        # Check if client wants SSE streaming
        accept_header = request.headers.get("accept", "")
        if "text/event-stream" in accept_header:
            return StreamingResponse(
                mcp_event_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                    "Access-Control-Allow-Methods": "*",
                }
            )
        else:
            # Return server info for regular GET requests
            return {
                "name": "Apple Music MCP Server",
                "version": "1.0.0",
                "protocol": "mcp",
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": False,
                    "logging": False
                }
            }
    
    elif request.method == "POST":
        # Handle JSON-RPC MCP requests
        if not mcp_request:
            # Try to parse from raw body if pydantic didn't catch it
            body = await request.body()
            try:
                data = json.loads(body.decode())
                mcp_request = MCPRequest(**data)
            except:
                raise HTTPException(status_code=400, detail="Invalid JSON-RPC request")
        
        return await handle_mcp_request(mcp_request)

async def handle_mcp_request(mcp_request: MCPRequest) -> Dict[str, Any]:
    """Handle MCP JSON-RPC requests"""
    try:
        if mcp_request.method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {},
                        "logging": {}
                    },
                    "serverInfo": {
                        "name": "Apple Music MCP Server",
                        "version": "1.0.0"
                    }
                }
            }
        
        elif mcp_request.method == "tools/list":
            tools = await mcp_handler.get_tools()
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": {"tools": tools}
            }
        
        elif mcp_request.method == "tools/call":
            if not mcp_request.params:
                raise ValueError("Missing parameters for tool call")
            
            tool_name = mcp_request.params.get("name")
            arguments = mcp_request.params.get("arguments", {})
            
            if not tool_name:
                raise ValueError("Missing tool name")
            
            print(f"DEBUG: Calling tool '{tool_name}' with arguments: {arguments}")
            
            try:
                result = await mcp_handler.handle_tool_call(tool_name, arguments)
                print(f"DEBUG: Tool call successful, result type: {type(result)}")
            except Exception as e:
                print(f"ERROR: Tool call failed - {type(e).__name__}: {e}")
                import traceback
                print(f"ERROR: Full traceback:\n{traceback.format_exc()}")
                raise
            
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2)
                        }
                    ]
                }
            }
        
        else:
            return {
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {mcp_request.method}"
                }
            }
    
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": mcp_request.id,
            "error": {
                "code": -32000,
                "message": str(e)
            }
        }

async def mcp_event_stream() -> AsyncIterator[str]:
    """Generate MCP event stream for SSE connections"""
    try:
        # Send initial connection acknowledgment
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"
        
        # Keep connection alive with periodic heartbeats
        while True:
            heartbeat = {
                "type": "heartbeat",
                "timestamp": datetime.utcnow().isoformat()
            }
            yield f"data: {json.dumps(heartbeat)}\n\n"
            await asyncio.sleep(30)
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        error_msg = {"type": "error", "message": str(e)}
        yield f"data: {json.dumps(error_msg)}\n\n"

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "services": {
            "server": "online"
        }
    }

# MCP Protocol Endpoints
@app.get("/mcp/tools")
async def get_tools():
    """Get available MCP tools"""
    try:
        tools = await mcp_handler.get_tools()
        return {"tools": tools}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/mcp/call-tool")
async def call_tool(request: ToolCallRequest):
    """Call an MCP tool"""
    try:
        result = await mcp_handler.handle_tool_call(request.name, request.arguments)
        return {"result": result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )