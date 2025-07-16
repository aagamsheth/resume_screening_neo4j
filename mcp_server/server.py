"""
Gets context of the projects and skills from google and extract keywords from it.
"""

import os
import requests
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

# Initialize FastMCP server
TRANSPORT = os.getenv("TRANSPORT", "sse")
mcp = FastMCP(
    name="get_context_mcp",
    host="0.0.0.0",
    port=8050
)


google_api_key = os.environ.get('GOOGLE_API_KEY')
google_search_engine_id = os.environ.get('GOOGLE_SEARCH_ENGINE_ID')
# Fetch Context From Google CSE
def fetch_context_from_google_cse(query: str, google_api_key: str, google_search_engine_id: str) -> Dict[str, Any]:
    """
    Fetch information from Google Custom Search Engine API.

    Args:
        query (str): The search query
        api_key (str): Google API key
        search_engine_id (str): Programmable Search Engine ID (cx)

    Returns:
        Dict[str, Any]: Structured information extracted from search results
    """
    search_url = "https://www.googleapis.com/customsearch/v1"

    params = {
        "q": query,
        "key": google_api_key,
        "cx": google_search_engine_id,
        "num": 10  # Max results per request
    }

    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })

        if not results:
            return {
                "query": query,
                "results": [],
                "summary": f"No results found for '{query}'."
            }

        summary = f"Search results for '{query}':\n\n"
        for i, result in enumerate(results[:5], 1):  # Limit to top 5
            summary += f"{i}. {result['title']}\n"
            summary += f"   {result['snippet']}\n\n"

        return {
            "query": query,
            "results": results,
            "summary": summary
        }

    except requests.RequestException as e:
        raise Exception(f"Failed to fetch search results: {str(e)}")
import requests
from typing import Dict, Any

@mcp.tool()
def get_context(context: str) -> Dict[str, Any]:
    """
    Get detailed context information that helps resume screening.
    
    Args:
        context (str): The context/prompt is of people's resume.
        
    Returns:
        Dict[str, Any]: Detailed information about the context to more accurately help HR and talent acquisition people in screening.
    """
    
    search_results_google = fetch_context_from_google_cse(context, google_api_key, google_search_engine_id)
    
    # Process the search results to create enhanced context
    enhanced_context = {
        "original_query": context,
        "search_results_google": search_results_google["results"][:5],  
        "enhanced_description": search_results_google["summary"],
        "relevant_keywords_google": extract_keywords(search_results_google),
    }
    
    return enhanced_context

def extract_keywords(search_results: Dict[str, Any]) -> list:
    """
    Extract relevant keywords from search results.
    
    Args:
        search_results (Dict[str, Any]): The Google search results
        
    Returns:
        list: List of relevant keywords
    """
    # Simple keyword extraction from titles and snippets
    keywords = set()
    
    # Process all results
    for result in search_results.get("results", []):
        # Add words from title (excluding common words)
        if "title" in result:
            for word in result["title"].lower().split():
                if len(word) > 4 and word not in {"and", "or", "the", "in", "on", "at", "with", "from", "to", "for"}:
                    keywords.add(word)
        
        # Add words from snippet
        if "snippet" in result:
            for word in result["snippet"].lower().split():
                if len(word) > 4 and word not in {"and", "or", "the", "in", "on", "at", "with", "from", "to", "for"}:
                    keywords.add(word)
    
    return list(keywords)

if __name__ == "__main__":
    print(f"Starting MCP server with {TRANSPORT} transport...")
    mcp.run(transport=TRANSPORT)