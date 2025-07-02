from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uvicorn
from typing import Dict, Any
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
class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

@app.get("/")
async def root():
    return {"message": "Apple Music MCP Server", "version": "1.0.0"}

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