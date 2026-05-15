"""
RepoMind Analyzer
Analyzes repository structure and generates insights using IBM Granite model via watsonx.ai
"""

import os
import json
from typing import Dict, Optional
import httpx
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Configuration
WATSONX_API_KEY = os.getenv("WATSONX_API_KEY")
WATSONX_PROJECT_ID = os.getenv("WATSONX_PROJECT_ID")
WATSONX_URL = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")
MODEL_ID = "ibm/granite-3-8b-instruct"
API_TIMEOUT = 120  # seconds


def _create_prompt(repo_data: Dict, analysis_type: str) -> str:
    """
    Create a prompt for the AI model based on analysis type.
    
    Args:
        repo_data: Dictionary with file_tree and file_contents
        analysis_type: One of 'architecture', 'modules', 'flows'
    
    Returns:
        Formatted prompt string
    """
    file_tree = repo_data.get("file_tree", [])
    file_contents = repo_data.get("file_contents", {})
    
    # Create a summary of the repository structure
    tree_summary = "\n".join(f"- {path}" for path in file_tree[:100])
    if len(file_tree) > 100:
        tree_summary += f"\n... and {len(file_tree) - 100} more files"
    
    # Include key file contents (README, config files, main entry points)
    key_files = []
    priority_files = ['README.md', 'readme.md', 'package.json', 'requirements.txt', 
                     'setup.py', 'pyproject.toml', 'main.py', 'app.py', 'index.js', 
                     'index.ts', 'server.js', 'server.ts']
    
    for filename in priority_files:
        for path, content in file_contents.items():
            if path.lower().endswith(filename.lower()):
                # Truncate long files
                truncated_content = content[:2000] + "..." if len(content) > 2000 else content
                key_files.append(f"\n### {path}\n```\n{truncated_content}\n```")
                break
    
    key_files_text = "\n".join(key_files[:5])  # Limit to 5 key files
    
    # Create prompts based on analysis type
    if analysis_type == "architecture":
        return f"""Analyze this repository and provide a comprehensive architecture summary.

Repository File Structure:
{tree_summary}

Key Files:
{key_files_text}

Please provide:
1. Overall purpose and type of project (web app, library, CLI tool, etc.)
2. Primary programming language(s) and frameworks used
3. Tech stack (frontend, backend, database, etc.)
4. Architecture pattern (MVC, microservices, monolithic, etc.)
5. Key dependencies and technologies

Keep the response concise but informative (3-5 paragraphs)."""

    elif analysis_type == "modules":
        return f"""Analyze this repository's structure and identify the main modules/components.

Repository File Structure:
{tree_summary}

Key Files:
{key_files_text}

Please provide a breakdown of the main folders/modules:
- List 5-8 main directories or logical modules
- For each module, explain its purpose and what it contains
- Describe how modules relate to each other

Format as a structured list with clear descriptions."""

    elif analysis_type == "flows":
        return f"""Analyze this repository and explain 2-3 key user flows or processes.

Repository File Structure:
{tree_summary}

Key Files:
{key_files_text}

Please identify and explain 2-3 important flows in this codebase, such as:
- Authentication/authorization flow
- API request handling
- Data processing pipeline
- User interaction flow
- Build/deployment process

For each flow:
1. Name the flow
2. Describe the step-by-step process
3. Mention key files/functions involved

Keep explanations clear and practical."""

    else:
        raise ValueError(f"Unknown analysis type: {analysis_type}")


def _get_iam_token(api_key: str) -> Optional[str]:
    """
    Exchange IBM Cloud API key for an IAM access token.
    
    Args:
        api_key: IBM Cloud API key
    
    Returns:
        IAM access token or None if error
    """
    iam_url = "https://iam.cloud.ibm.com/identity/token"
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "urn:ibm:params:oauth:grant-type:apikey",
        "apikey": api_key
    }
    
    try:
        with httpx.Client(timeout=30) as client:
            response = client.post(iam_url, headers=headers, data=data)
            response.raise_for_status()
            
            result = response.json()
            return result.get("access_token")
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error getting IAM token: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"Request error getting IAM token: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error getting IAM token: {str(e)}")
        return None


def _call_watsonx_api(prompt: str) -> Optional[str]:
    """
    Make an API call to watsonx.ai using the IBM Granite model.
    
    Args:
        prompt: The prompt to send to the model
    
    Returns:
        Generated text response or None if error
    """
    if not WATSONX_API_KEY:
        raise ValueError("WATSONX_API_KEY environment variable not set")
    
    if not WATSONX_PROJECT_ID:
        raise ValueError("WATSONX_PROJECT_ID environment variable not set")
    
    # Get IAM token
    iam_token = _get_iam_token(WATSONX_API_KEY)
    if not iam_token:
        print("Failed to obtain IAM token")
        return None
    
    # Construct the API endpoint
    endpoint = f"{WATSONX_URL}/ml/v1/text/generation?version=2023-05-29"
    
    # Prepare headers with IAM token
    headers = {
        "Authorization": f"Bearer {iam_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # Prepare request body
    body = {
        "input": prompt,
        "parameters": {
            "decoding_method": "greedy",
            "max_new_tokens": 1000,
            "min_new_tokens": 50,
            "temperature": 0.7,
            "top_k": 50,
            "top_p": 1,
            "repetition_penalty": 1.1
        },
        "model_id": MODEL_ID,
        "project_id": WATSONX_PROJECT_ID
    }
    
    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            response = client.post(endpoint, headers=headers, json=body)
            response.raise_for_status()
            
            result = response.json()
            
            # Extract generated text from response
            if "results" in result and len(result["results"]) > 0:
                return result["results"][0].get("generated_text", "").strip()
            else:
                return None
                
    except httpx.HTTPStatusError as e:
        print(f"HTTP error calling watsonx.ai API: {e.response.status_code} - {e.response.text}")
        return None
    except httpx.RequestError as e:
        print(f"Request error calling watsonx.ai API: {str(e)}")
        return None
    except Exception as e:
        print(f"Unexpected error calling watsonx.ai API: {str(e)}")
        return None


def analyze_repo(repo_data: Dict) -> Dict:
    """
    Analyze a repository using IBM Granite model via watsonx.ai.
    
    Makes 3 separate API calls to generate:
    1. architecture_summary: Overall tech stack, structure, and purpose
    2. module_breakdown: List of main folders/modules and what each does
    3. key_flows: Explanation of 2-3 key flows
    
    Args:
        repo_data: Dictionary returned by fetch_repo() containing:
            - file_tree: List of file paths
            - file_contents: Dictionary of file contents
            - error: Error message if any
    
    Returns:
        Dictionary with:
            - architecture_summary: str
            - module_breakdown: str
            - key_flows: str
            - error: str or None
    
    Example:
        >>> repo_data = fetch_repo("https://github.com/user/repo")
        >>> analysis = analyze_repo(repo_data)
        >>> print(analysis['architecture_summary'])
    """
    # Check if repo_data has an error
    if repo_data.get("error"):
        return {
            "architecture_summary": "",
            "module_breakdown": "",
            "key_flows": "",
            "error": f"Cannot analyze repository: {repo_data['error']}"
        }
    
    # Check if we have data to analyze
    if not repo_data.get("file_tree") and not repo_data.get("file_contents"):
        return {
            "architecture_summary": "",
            "module_breakdown": "",
            "key_flows": "",
            "error": "No repository data to analyze"
        }
    
    try:
        # Generate architecture summary
        print("Generating architecture summary...")
        arch_prompt = _create_prompt(repo_data, "architecture")
        architecture_summary = _call_watsonx_api(arch_prompt)
        
        if not architecture_summary:
            return {
                "architecture_summary": "",
                "module_breakdown": "",
                "key_flows": "",
                "error": "Failed to generate architecture summary"
            }
        
        # Generate module breakdown
        print("Generating module breakdown...")
        module_prompt = _create_prompt(repo_data, "modules")
        module_breakdown = _call_watsonx_api(module_prompt)
        
        if not module_breakdown:
            return {
                "architecture_summary": architecture_summary,
                "module_breakdown": "",
                "key_flows": "",
                "error": "Failed to generate module breakdown"
            }
        
        # Generate key flows
        print("Generating key flows analysis...")
        flows_prompt = _create_prompt(repo_data, "flows")
        key_flows = _call_watsonx_api(flows_prompt)
        
        if not key_flows:
            return {
                "architecture_summary": architecture_summary,
                "module_breakdown": module_breakdown,
                "key_flows": "",
                "error": "Failed to generate key flows analysis"
            }
        
        return {
            "architecture_summary": architecture_summary,
            "module_breakdown": module_breakdown,
            "key_flows": key_flows,
            "error": None
        }
    
    except Exception as e:
        return {
            "architecture_summary": "",
            "module_breakdown": "",
            "key_flows": "",
            "error": f"Analysis failed: {str(e)}"
        }


# Example usage and testing
if __name__ == "__main__":
    from repo_handler import fetch_repo
    
    # Test with a small public repository
    test_url = "https://github.com/octocat/Hello-World"
    
    print("Fetching repository...")
    repo_data = fetch_repo(test_url)
    
    if repo_data.get("error"):
        print(f"Error fetching repo: {repo_data['error']}")
    else:
        print(f"Repository fetched: {len(repo_data['file_tree'])} files")
        
        print("\nAnalyzing repository...")
        analysis = analyze_repo(repo_data)
        
        if analysis.get("error"):
            print(f"Error: {analysis['error']}")
        else:
            print("\n=== ARCHITECTURE SUMMARY ===")
            print(analysis['architecture_summary'])
            print("\n=== MODULE BREAKDOWN ===")
            print(analysis['module_breakdown'])
            print("\n=== KEY FLOWS ===")
            print(analysis['key_flows'])

# Made with Bob