"""
RepoMind FastAPI Backend
Main application entry point with API endpoints
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Dict, List, Optional, Any
import os
from dotenv import load_dotenv

from repo_handler import fetch_repo
from analyzer import analyze_repo, _call_watsonx_api

# Load environment variables from .env file
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="RepoMind API",
    description="Backend API for analyzing GitHub repositories",
    version="1.0.0"
)

# Add CORS middleware to allow all origins (for frontend development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)


# Request/Response Models
class AnalyzeRequest(BaseModel):
    """Request model for repository analysis"""
    github_url: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "github_url": "https://github.com/octocat/Hello-World"
            }
        }


class AnalyzeResponse(BaseModel):
    """Response model for repository analysis"""
    file_tree: List[str]
    file_contents: Dict[str, str]
    architecture_summary: str
    module_breakdown: str
    key_flows: str
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "file_tree": ["README.md", "src/main.py"],
                "file_contents": {
                    "README.md": "# Hello World\nThis is a sample repository."
                },
                "architecture_summary": "This is a Python web application...",
                "module_breakdown": "Main modules include...",
                "key_flows": "Key flows: 1. Authentication...",
                "error": None
            }
        }


class ChatRequest(BaseModel):
    """Request model for chat endpoint"""
    github_url: str
    question: str
    repo_data: Dict[str, Any]
    
    class Config:
        json_schema_extra = {
            "example": {
                "github_url": "https://github.com/octocat/Hello-World",
                "question": "What is the main purpose of this repository?",
                "repo_data": {
                    "file_tree": ["README.md"],
                    "file_contents": {"README.md": "# Hello World"}
                }
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint"""
    answer: str
    error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "This repository is a simple Hello World example...",
                "error": None
            }
        }


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok"
            }
        }


# API Endpoints
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint to verify the API is running.
    
    Returns:
        HealthResponse: Status of the API
    """
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse, tags=["Repository"])
async def analyze_repository(request: AnalyzeRequest):
    """
    Analyze a GitHub repository by cloning it, extracting file structure and contents,
    and generating AI-powered insights using IBM Granite model.
    
    Args:
        request: AnalyzeRequest containing the GitHub repository URL
    
    Returns:
        AnalyzeResponse: Repository file tree, file contents, AI analysis, and any errors
    
    Raises:
        HTTPException: If the request is invalid or analysis fails
    """
    try:
        # Validate GitHub URL format
        github_url = request.github_url.strip()
        
        if not github_url:
            raise HTTPException(
                status_code=400,
                detail="GitHub URL cannot be empty"
            )
        
        if not github_url.startswith(("https://github.com/", "http://github.com/")):
            raise HTTPException(
                status_code=400,
                detail="Invalid GitHub URL. Must start with https://github.com/"
            )
        
        # Step 1: Call fetch_repo from repo_handler
        repo_data = fetch_repo(github_url)
        
        # Check if there was an error during fetching
        if repo_data.get("error"):
            # Return 404 for repository not found
            if "not found" in repo_data["error"].lower():
                raise HTTPException(
                    status_code=404,
                    detail=repo_data["error"]
                )
            # Return 401 for authentication issues
            elif "authentication" in repo_data["error"].lower() or "private" in repo_data["error"].lower():
                raise HTTPException(
                    status_code=401,
                    detail=repo_data["error"]
                )
            # Return 500 for other errors
            else:
                raise HTTPException(
                    status_code=500,
                    detail=repo_data["error"]
                )
        
        # Step 2: Call analyze_repo with the fetched data
        analysis = analyze_repo(repo_data)
        
        # Combine repo data and analysis into one response
        return {
            "file_tree": repo_data.get("file_tree", []),
            "file_contents": repo_data.get("file_contents", {}),
            "architecture_summary": analysis.get("architecture_summary", ""),
            "module_breakdown": analysis.get("module_breakdown", ""),
            "key_flows": analysis.get("key_flows", ""),
            "error": analysis.get("error")
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat_about_repo(request: ChatRequest):
    """
    Answer questions about a repository using IBM Granite model via watsonx.ai.
    
    Args:
        request: ChatRequest containing github_url, question, and repo_data
    
    Returns:
        ChatResponse: AI-generated answer to the question
    
    Raises:
        HTTPException: If the request is invalid or chat fails
    """
    try:
        # Validate inputs
        if not request.question or not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="Question cannot be empty"
            )
        
        if not request.repo_data:
            raise HTTPException(
                status_code=400,
                detail="Repository data is required"
            )
        
        # Extract repo data
        file_tree = request.repo_data.get("file_tree", [])
        file_contents = request.repo_data.get("file_contents", {})
        
        if not file_tree and not file_contents:
            raise HTTPException(
                status_code=400,
                detail="Repository data is empty or invalid"
            )
        
        # Create a summary of the repository structure
        tree_summary = "\n".join(f"- {path}" for path in file_tree[:50])
        if len(file_tree) > 50:
            tree_summary += f"\n... and {len(file_tree) - 50} more files"
        
        # Include key file contents
        key_files = []
        for path, content in list(file_contents.items())[:5]:
            truncated_content = content[:1000] + "..." if len(content) > 1000 else content
            key_files.append(f"\n### {path}\n```\n{truncated_content}\n```")
        
        key_files_text = "\n".join(key_files)
        
        # Create prompt for watsonx.ai
        prompt = f"""You are a helpful AI assistant analyzing a GitHub repository.

Repository: {request.github_url}

Repository File Structure:
{tree_summary}

Key Files:
{key_files_text}

User Question: {request.question}

Please provide a clear, concise, and helpful answer based on the repository structure and contents shown above. If the information needed to answer the question is not available in the provided data, say so."""
        
        # Call watsonx.ai API
        answer = _call_watsonx_api(prompt)
        
        if not answer:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate answer from AI model"
            )
        
        return {
            "answer": answer,
            "error": None
        }
    
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    
    except Exception as e:
        # Catch any unexpected errors
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint with API information.
    
    Returns:
        dict: Welcome message and API information
    """
    return {
        "message": "Welcome to RepoMind API",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "analyze": "/analyze",
            "chat": "/chat",
            "docs": "/docs"
        }
    }


# Run the application
if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.getenv("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True  # Enable auto-reload during development
    )

# Made with Bob
