import os
import datetime
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, quote
from fastmcp import FastMCP
from typing import Optional
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# Initialize FastMCP server
mcp = FastMCP("NeuroWeave Core Tools")

# Define safe directory boundaries
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def check_safe_path(path: str) -> str:
    """Ensure path is within the safe project directory."""
    abs_path = os.path.abspath(path)
    if not abs_path.startswith(BASE_DIR):
        # Allow state folder inside base dir or app data directory
        app_data_dir = os.path.abspath("/Users/sahil/.gemini/antigravity")
        if abs_path.startswith(app_data_dir):
            return abs_path
        raise ValueError(f"Access Denied: Path {path} is outside of project workspace.")
    return abs_path

@mcp.tool()
async def web_search(query: str) -> str:
    """
    Search the web for key facts, evidence, and articles using DuckDuckGo.
    Returns list of matching titles, urls, and snippets.
    """
    url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            
        soup = BeautifulSoup(r.text, "html.parser")
        divs = soup.find_all("div", class_="result")
        
        results = []
        for div in divs[:6]:
            title_a = div.find("a", class_="result__a")
            snippet_a = div.find("a", class_="result__snippet")
            
            if not title_a:
                continue
                
            title = title_a.text.strip()
            raw_href = title_a.get("href", "")
            
            # Extract clean destination URL from DDG redirect url
            clean_href = raw_href
            if "uddg=" in raw_href:
                parsed = urlparse("https:" + raw_href if raw_href.startswith("//") else raw_href)
                qs = parse_qs(parsed.query)
                if "uddg" in qs:
                    clean_href = qs["uddg"][0]
            
            snippet = snippet_a.text.strip() if snippet_a else ""
            results.append(f"Title: {title}\nURL: {clean_href}\nSnippet: {snippet}\n---")
            
        if not results:
            return f"No results found for query: '{query}'."
            
        return "\n".join(results)
    except Exception as e:
        return f"Error executing web search: {str(e)}"

@mcp.tool()
async def fetch_url(url: str) -> str:
    """
    Fetch the content of a web page and convert it into clean, readable text.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Remove non-content elements
        for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
            element.extract()
            
        # Extract main text
        lines = (line.strip() for line in soup.get_text().splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)
        
        # Cap text size to prevent exceeding token limit (e.g. 50000 chars)
        if len(text) > 25000:
            text = text[:25000] + "\n\n... [Content Truncated due to Length] ..."
            
        return f"Content of URL: {url}\n\n{text}"
    except Exception as e:
        return f"Error fetching URL {url}: {str(e)}"

@mcp.tool()
async def get_time() -> str:
    """
    Get the current UTC system date and time.
    """
    return f"Current System Time (UTC): {datetime.datetime.utcnow().isoformat()}"

@mcp.tool()
async def read_file(path: str) -> str:
    """
    Read the contents of a local file safely.
    """
    try:
        safe_path = check_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Error: File '{path}' does not exist."
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{path}': {str(e)}"

@mcp.tool()
async def create_file(path: str, content: str) -> str:
    """
    Create a new local file with specified content safely.
    """
    try:
        safe_path = check_safe_path(path)
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{path}' created."
    except Exception as e:
        return f"Error creating file '{path}': {str(e)}"

@mcp.tool()
async def update_file(path: str, content: str) -> str:
    """
    Overwrite an existing local file safely.
    """
    try:
        safe_path = check_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Error: File '{path}' does not exist to update. Use create_file instead."
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Success: File '{path}' updated."
    except Exception as e:
        return f"Error updating file '{path}': {str(e)}"

@mcp.tool()
async def edit_file(path: str, content: str) -> str:
    """
    Alias for update_file to perform full modifications on local files safely.
    """
    return await update_file(path, content)

@mcp.tool()
async def list_dir(path: str) -> str:
    """
    List contents of a local directory safely.
    """
    try:
        safe_path = check_safe_path(path)
        if not os.path.exists(safe_path):
            return f"Error: Directory '{path}' does not exist."
        if not os.path.isdir(safe_path):
            return f"Error: '{path}' is not a directory."
            
        items = os.listdir(safe_path)
        out = []
        for item in items:
            full_item = os.path.join(safe_path, item)
            is_dir = os.path.isdir(full_item)
            marker = "[DIR] " if is_dir else "[FILE]"
            out.append(f"{marker} {item}")
            
        return "\n".join(out) if out else "Directory is empty."
    except Exception as e:
        return f"Error listing directory '{path}': {str(e)}"

@mcp.tool()
async def tavily_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily AI search engine.
    Returns structured results with titles, urls, and content snippets.
    Requires TAVILY_API_KEY in .env.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return "Error: TAVILY_API_KEY not set. Add it to .env file."

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results, include_answer=True)
        
        out = []
        if response.get("answer"):
            out.append(f"AI Summary: {response['answer']}\n")
        
        results = response.get("results", [])
        if not results:
            return f"No Tavily results found for: '{query}'."
        
        for r in results:
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            content = r.get("content", "")[:500]
            out.append(f"Title: {title}\nURL: {url}\nContent: {content}\n---")
        
        return "\n".join(out)
    except Exception as e:
        return f"Tavily search error: {str(e)}"

@mcp.tool()
async def tavily_search_context(query: str, max_results: int = 5) -> str:
    """
    Search the web using Tavily with raw content extraction.
    Returns full raw content for deeper analysis than tavily_search.
    Requires TAVILY_API_KEY in .env.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        return "Error: TAVILY_API_KEY not set. Add it to .env file."

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=max_results, include_raw_content=True)
        
        out = []
        if response.get("answer"):
            out.append(f"AI Summary: {response['answer']}\n")
        
        results = response.get("results", [])
        if not results:
            return f"No Tavily results found for: '{query}'."
        
        for r in results:
            title = r.get("title", "Untitled")
            url = r.get("url", "")
            raw = r.get("raw_content", "") or r.get("content", "")
            out.append(f"=== {title} ===\nURL: {url}\n{raw[:2000]}\n===")
        
        return "\n".join(out)
    except Exception as e:
        return f"Tavily context search error: {str(e)}"

if __name__ == "__main__":
    # Start the FastMCP server on stdio transport
    mcp.run()
