"""
title: Firecrawl Web Scraping and Search Pipe
author: Jonathan
author_url: https://github.com/jfhome
funding_url: https://github.com/open-webui
version: 1.0.0
required_open_webui_version: 0.4.3
license: MIT
description: Comprehensive web scraping, URL mapping, and search pipeline using Firecrawl API v1 with support for multiple output formats and advanced features.
requirements: requests
"""

import os
import json
import requests
import re
import traceback
from typing import List, Union, Generator, Iterator, Optional, Dict, Any
from pydantic import BaseModel, Field
from logging import getLogger

logger = getLogger(__name__)
logger.setLevel("DEBUG")

# Request and Response Models
class ScrapeRequest(BaseModel):
    url: str
    formats: List[str] = Field(default_factory=lambda: ["markdown"])
    onlyMainContent: bool = True
    includeTags: Optional[List[str]] = None
    removeTags: Optional[List[str]] = None
    waitFor: Optional[int] = None

class ScrapeResponse(BaseModel):
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

class MapRequest(BaseModel):
    url: str
    search: str = ""
    ignoreSitemap: bool = False
    sitemapOnly: bool = False
    includeSubdomains: bool = False
    limit: int = 1000

class MapResponse(BaseModel):
    success: bool
    links: List[str]
    error: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    format: str = "markdown"
    lang: str = ""
    country: str = ""
    timeRange: Optional[str] = None
    categories: Optional[List[str]] = None

class SearchResponse(BaseModel):
    success: bool
    data: List[Dict[str, Any]]
    error: Optional[str] = None

class CrawlRequest(BaseModel):
    url: str
    limit: int = 100
    depth: Optional[int] = None
    maxPages: Optional[int] = None
    allowBackwardLinks: bool = False
    allowExternalLinks: bool = False
    includeTags: Optional[List[str]] = None
    excludeTags: Optional[List[str]] = None
    ignoreSitemap: bool = False
    sitemapOnly: bool = False
    waitFor: Optional[int] = None

class CrawlResponse(BaseModel):
    success: bool
    jobId: Optional[str] = None
    status: Optional[str] = None
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None

class FirecrawlClient:
    def __init__(self, api_key: str, debug: bool = False):
        self.api_key = api_key
        self.base_url = "https://api.firecrawl.dev/v1"
        self.debug = debug

    def headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Origin": "openwebui",
            "X-Origin-Type": "integration",
        }

    def scrape_url(self, request: ScrapeRequest) -> ScrapeResponse:
        endpoint = "/scrape"
        url = f"{self.base_url}{endpoint}"
        headers = self.headers()

        if self.debug:
            logger.debug(f"Scrape request: {json.dumps(request.model_dump(), indent=2)}")
            logger.debug(f"Endpoint: {url}")
            logger.debug(f"Using API key: {self.api_key[:4]}...{self.api_key[-4:] if len(self.api_key) > 8 else ''}")

        try:
            payload = request.model_dump(exclude_none=True)

            response = requests.post(url, json=payload, headers=headers)

            if self.debug:
                logger.debug(f"Response status code: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")

            response.raise_for_status()

            response_data = response.json()
            if self.debug:
                logger.debug(f"Response data keys: {list(response_data.keys())}")

            return ScrapeResponse(**response_data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Scrape request failed: {str(e)}"
            if self.debug:
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status code: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                logger.error(traceback.format_exc())
            return ScrapeResponse(success=False, data={}, error=error_msg)

    def map_urls(self, request: MapRequest) -> MapResponse:
        endpoint = "/map"
        url = f"{self.base_url}{endpoint}"
        headers = self.headers()

        if self.debug:
            logger.debug(f"Map request: {json.dumps(request.model_dump(), indent=2)}")
            logger.debug(f"Endpoint: {url}")

        try:
            payload = {
                "url": request.url,
                "search": request.search,
                "ignoreSitemap": request.ignoreSitemap,
                "sitemapOnly": request.sitemapOnly,
                "includeSubdomains": request.includeSubdomains,
                "limit": request.limit
            }

            response = requests.post(url, json=payload, headers=headers)

            if self.debug:
                logger.debug(f"Response status code: {response.status_code}")

            response.raise_for_status()

            response_data = response.json()
            if self.debug:
                logger.debug(f"Map response with {len(response_data.get('links', []))} URLs")

            return MapResponse(**response_data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Map request failed: {str(e)}"
            if self.debug:
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status code: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                logger.error(traceback.format_exc())
            return MapResponse(success=False, links=[], error=error_msg)

    def search_web(self, request: SearchRequest) -> SearchResponse:
        endpoint = "/search"
        url = f"{self.base_url}{endpoint}"
        headers = self.headers()

        if self.debug:
            logger.debug(f"Search request: {json.dumps(request.model_dump(), indent=2)}")
            logger.debug(f"Endpoint: {url}")

        try:
            payload = {
                "query": request.query,
                "limit": request.limit,
                "format": request.format
            }

            # Add optional parameters if provided
            if request.lang:
                payload["lang"] = request.lang
            if request.country:
                payload["country"] = request.country
            if request.timeRange:
                payload["timeRange"] = request.timeRange
            if request.categories:
                payload["categories"] = request.categories

            response = requests.post(url, json=payload, headers=headers)

            if self.debug:
                logger.debug(f"Response status code: {response.status_code}")

            response.raise_for_status()

            response_data = response.json()
            if self.debug:
                logger.debug(f"Search response with {len(response_data.get('data', []))} results")

            return SearchResponse(**response_data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Search request failed: {str(e)}"
            if self.debug:
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status code: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                logger.error(traceback.format_exc())
            return SearchResponse(success=False, data=[], error=error_msg)

    def start_crawl(self, request: CrawlRequest) -> CrawlResponse:
        endpoint = "/crawl"
        url = f"{self.base_url}{endpoint}"
        headers = self.headers()

        if self.debug:
            logger.debug(f"Crawl request: {json.dumps(request.model_dump(), indent=2)}")
            logger.debug(f"Endpoint: {url}")

        try:
            payload = request.model_dump(exclude_none=True)

            response = requests.post(url, json=payload, headers=headers)

            if self.debug:
                logger.debug(f"Response status code: {response.status_code}")

            response.raise_for_status()

            response_data = response.json()
            if self.debug:
                logger.debug(f"Crawl started with job ID: {response_data.get('jobId')}")

            return CrawlResponse(**response_data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Crawl request failed: {str(e)}"
            if self.debug:
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status code: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                logger.error(traceback.format_exc())
            return CrawlResponse(success=False, error=error_msg)

    def get_crawl_status(self, job_id: str) -> CrawlResponse:
        endpoint = f"/crawl/{job_id}"
        url = f"{self.base_url}{endpoint}"
        headers = self.headers()

        if self.debug:
            logger.debug(f"Getting crawl status for job: {job_id}")
            logger.debug(f"Endpoint: {url}")

        try:
            response = requests.get(url, headers=headers)

            if self.debug:
                logger.debug(f"Response status code: {response.status_code}")

            response.raise_for_status()

            response_data = response.json()
            if self.debug:
                logger.debug(f"Crawl status: {response_data.get('status')}")

            return CrawlResponse(**response_data)
        except requests.exceptions.RequestException as e:
            error_msg = f"Get crawl status failed: {str(e)}"
            if self.debug:
                logger.error(error_msg)
                if hasattr(e, 'response') and e.response:
                    logger.error(f"Response status code: {e.response.status_code}")
                    logger.error(f"Response body: {e.response.text}")
                logger.error(traceback.format_exc())
            return CrawlResponse(success=False, error=error_msg)


class Pipe:
    class Valves(BaseModel):
        FIRECRAWL_API_KEY: str = Field(default="", description="Firecrawl API key")
        DEFAULT_SCRAPE_FORMATS: str = Field(default="markdown", description="Default output formats for scraping (comma-separated: markdown,html,rawHtml,screenshot,links,json)")
        DEFAULT_MAP_LIMIT: int = Field(default=1000, description="Default maximum number of URLs to map")
        DEFAULT_SEARCH_LIMIT: int = Field(default=10, description="Default number of search results")
        DEFAULT_CRAWL_LIMIT: int = Field(default=100, description="Default crawl limit")
        IGNORE_SITEMAP: bool = Field(default=False, description="Ignore sitemap.xml when mapping URLs")
        SITEMAP_ONLY: bool = Field(default=False, description="Only use sitemap.xml when mapping URLs")
        INCLUDE_SUBDOMAINS: bool = Field(default=False, description="Include subdomains when mapping URLs")
        ONLY_MAIN_CONTENT: bool = Field(default=True, description="Extract only main content when scraping")
        DEBUG_MODE: bool = Field(default=False, description="Enable debug logging")

    def __init__(self):
        self.name = "Firecrawl Web Scraping Pipeline"
        self.type = "tool"  # This is a tool pipe, not a manifold pipe

        # Initialize valve parameters
        self.valves = self.Valves(
            **{k: os.getenv(k, v.default) for k, v in self.Valves.model_fields.items()}
        )

        # Initialize client
        self.client = None

        # Print valve configuration
        for k, v in self.valves.model_dump().items():
            if k == "FIRECRAWL_API_KEY" and v:
                logger.debug(f"{k}: {v[:4]}...{v[-4:] if len(v) > 8 else ''}")
            elif v:
                logger.debug(f"{k}: {v}")
            else:
                logger.debug(f"{k}: not set")

    async def on_startup(self):
        logger.debug(f"on_startup:{self.name}")
        if not self.valves.FIRECRAWL_API_KEY:
            logger.warning("FIRECRAWL_API_KEY not set. Pipeline will not function correctly.")
        else:
            self.client = FirecrawlClient(
                api_key=self.valves.FIRECRAWL_API_KEY,
                debug=self.valves.DEBUG_MODE
            )

    async def on_shutdown(self):
        logger.debug(f"on_shutdown:{self.name}")

    def _extract_url_from_message(self, message: str) -> Optional[str]:
        """Extract URL from user message"""
        url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
        urls = re.findall(url_pattern, message)

        if self.valves.DEBUG_MODE:
            logger.debug(f"Extracted URLs from message: {urls}")

        return urls[0] if urls else None

    def _extract_search_query(self, message: str) -> Optional[str]:
        """Extract search query from user message"""
        # Look for search commands
        search_patterns = [
            r'search for "(.+?)"',
            r'search "(.+?)"',
            r'find "(.+?)"',
            r'look for "(.+?)"',
            r'scrape search "(.+?)"',
        ]

        for pattern in search_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                query = match.group(1)
                if self.valves.DEBUG_MODE:
                    logger.debug(f"Extracted search query: {query}")
                return query

        if self.valves.DEBUG_MODE:
            logger.debug("No search query found in message")

        return None

    def _determine_operation(self, message: str) -> str:
        """Determine what operation to perform based on the message"""
        message_lower = message.lower()

        # Check for explicit commands
        if any(cmd in message_lower for cmd in ['map', 'mapping', 'urls', 'links from']):
            return 'map'
        elif any(cmd in message_lower for cmd in ['search', 'find', 'look for']):
            return 'search'
        elif any(cmd in message_lower for cmd in ['crawl', 'crawling']):
            return 'crawl'
        elif self._extract_url_from_message(message):
            return 'scrape'
        else:
            return 'unknown'

    def _format_scrape_result(self, response: ScrapeResponse, formats: List[str]) -> str:
        """Format scrape response for display"""
        if not response.success or not response.data:
            return f"❌ Scraping failed: {response.error or 'Unknown error'}"

        result = "📄 **Scraped Content**\n\n"

        # Add metadata if available
        if 'metadata' in response.data:
            meta = response.data['metadata']
            result += f"**Title:** {meta.get('title', 'N/A')}\n"
            result += f"**URL:** {meta.get('sourceURL', 'N/A')}\n"
            result += f"**Description:** {meta.get('description', 'N/A')}\n\n"

        # Add content based on requested formats
        for fmt in formats:
            if fmt in response.data:
                content = response.data[fmt]
                if fmt == 'markdown':
                    result += f"## Markdown Content\n\n{content}\n\n"
                elif fmt == 'html':
                    result += f"## HTML Content\n\n```html\n{content}\n```\n\n"
                elif fmt == 'rawHtml':
                    result += f"## Raw HTML Content\n\n```html\n{content[:1000]}...\n```\n\n"
                elif fmt == 'links' and isinstance(content, list):
                    result += f"## Discovered Links ({len(content)})\n\n"
                    result += "\n".join(f"- {link}" for link in content[:20])
                    if len(content) > 20:
                        result += f"\n... and {len(content) - 20} more links"
                    result += "\n\n"
                elif fmt == 'json' and isinstance(content, dict):
                    result += f"## Structured Data\n\n```json\n{json.dumps(content, indent=2)}\n```\n\n"

        return result

    def _format_map_result(self, response: MapResponse, search_term: str = "") -> str:
        """Format map response for display"""
        if not response.success:
            return f"❌ URL mapping failed: {response.error or 'Unknown error'}"

        result = "🗺️ **URL Mapping Results**\n\n"

        if search_term:
            result += f"Found {len(response.links)} URLs containing '{search_term}'.\n\n"
        else:
            result += f"Found {len(response.links)} URLs.\n\n"

        if response.links:
            result += "**Mapped URLs:**\n"
            for i, url in enumerate(response.links[:50], 1):
                result += f"{i}. {url}\n"

            if len(response.links) > 50:
                result += f"\n... and {len(response.links) - 50} more URLs"
        else:
            result += "No URLs found."

        return result

    def _format_search_result(self, response: SearchResponse) -> str:
        """Format search response for display"""
        if not response.success or not response.data:
            return f"❌ Search failed: {response.error or 'Unknown error'}"

        result = f"🔍 **Search Results** ({len(response.data)} found)\n\n"

        for i, item in enumerate(response.data, 1):
            result += f"**{i}. {item.get('title', 'No title')}**\n"
            result += f"URL: {item.get('url', 'N/A')}\n"

            if 'description' in item:
                result += f"Description: {item['description']}\n"

            if 'markdown' in item and item['markdown']:
                content = item['markdown']
                # Truncate content if too long
                if len(content) > 500:
                    content = content[:500] + "..."
                result += f"Content: {content}\n"

            result += "\n" + "="*50 + "\n\n"

        return result

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        Process the user message and perform Firecrawl operations
        """
        logger.debug(f"pipe:{__name__}")

        if self.valves.DEBUG_MODE:
            logger.debug(f"User message: {user_message}")
            logger.debug(f"Model ID: {model_id}")
            logger.debug(f"Body: {json.dumps(body, indent=2)}")

        if body.get("title", False):
            return "Firecrawl Web Scraping and Search Pipeline"

        # Check if API key is set
        if not self.valves.FIRECRAWL_API_KEY:
            return "❌ Error: FIRECRAWL_API_KEY not set. Please set it in your environment variables."

        if not self.client:
            return "❌ Error: Firecrawl client not initialized."

        # Handle debug commands
        if "debug on" in user_message.lower():
            self.valves.DEBUG_MODE = True
            self.client.debug = True
            return "🔧 Debug mode has been enabled. Detailed logs will now be shown."

        if "debug off" in user_message.lower():
            self.valves.DEBUG_MODE = False
            self.client.debug = False
            return "🔧 Debug mode has been disabled."

        if "debug status" in user_message.lower():
            status = "enabled" if self.valves.DEBUG_MODE else "disabled"
            return f"🔧 Debug mode is currently {status}."

        # Determine operation
        operation = self._determine_operation(user_message)

        try:
            if operation == 'scrape':
                # Scrape a single URL
                url = self._extract_url_from_message(user_message)
                if not url:
                    return "❌ No URL found in your message. Please provide a valid URL to scrape."

                # Parse requested formats
                formats = self.valves.DEFAULT_SCRAPE_FORMATS.split(',')
                formats = [fmt.strip() for fmt in formats if fmt.strip()]

                request = ScrapeRequest(
                    url=url,
                    formats=formats,
                    onlyMainContent=self.valves.ONLY_MAIN_CONTENT
                )

                response = self.client.scrape_url(request)
                return self._format_scrape_result(response, formats)

            elif operation == 'map':
                # Map URLs from a page
                url = self._extract_url_from_message(user_message)
                if not url:
                    return "❌ No URL found in your message. Please provide a valid URL to map."

                # Check for search term in the URL mapping context
                search_term = ""
                if 'containing' in user_message.lower() or 'with' in user_message.lower():
                    # Extract search term from phrases like "containing 'term'" or "with 'term'"
                    search_match = re.search(r"(?:containing|with)\s+['\"](.+?)['\"]", user_message, re.IGNORECASE)
                    if search_match:
                        search_term = search_match.group(1)

                request = MapRequest(
                    url=url,
                    search=search_term,
                    ignoreSitemap=self.valves.IGNORE_SITEMAP,
                    sitemapOnly=self.valves.SITEMAP_ONLY,
                    includeSubdomains=self.valves.INCLUDE_SUBDOMAINS,
                    limit=self.valves.DEFAULT_MAP_LIMIT
                )

                response = self.client.map_urls(request)
                return self._format_map_result(response, search_term)

            elif operation == 'search':
                # Search the web
                query = self._extract_search_query(user_message)
                if not query:
                    return "❌ No search query found. Try: 'search for \"your query\"'"

                request = SearchRequest(
                    query=query,
                    limit=self.valves.DEFAULT_SEARCH_LIMIT,
                    format="markdown"
                )

                response = self.client.search_web(request)
                return self._format_search_result(response)

            elif operation == 'crawl':
                # Start a crawl job
                url = self._extract_url_from_message(user_message)
                if not url:
                    return "❌ No URL found in your message. Please provide a valid URL to crawl."

                request = CrawlRequest(
                    url=url,
                    limit=self.valves.DEFAULT_CRAWL_LIMIT
                )

                response = self.client.start_crawl(request)
                if response.success and response.jobId:
                    return f"🕷️ **Crawl Started**\n\nJob ID: `{response.jobId}`\nStatus: {response.status or 'queued'}\n\nUse 'crawl status {response.jobId}' to check progress."
                else:
                    return f"❌ Crawl failed: {response.error or 'Unknown error'}"

            elif 'crawl status' in user_message.lower():
                # Check crawl status
                job_id_match = re.search(r'crawl status (\w+)', user_message, re.IGNORECASE)
                if not job_id_match:
                    return "❌ Please provide a job ID. Usage: 'crawl status <job_id>'"

                job_id = job_id_match.group(1)
                response = self.client.get_crawl_status(job_id)

                if response.success:
                    status = response.status or 'unknown'
                    result = f"🕷️ **Crawl Status: {job_id}**\n\nStatus: {status}\n"

                    if response.data and len(response.data) > 0:
                        result += f"Pages crawled: {len(response.data)}\n\n"
                        result += "**Recent pages:**\n"
                        for i, page in enumerate(response.data[-5:], 1):
                            result += f"{i}. {page.get('url', 'N/A')} ({page.get('status', 'unknown')})\n"
                    else:
                        result += "No pages crawled yet."

                    return result
                else:
                    return f"❌ Failed to get crawl status: {response.error or 'Unknown error'}"

            else:
                # Help message
                return """🤖 **Firecrawl Pipeline Help**

I can help you with web scraping, URL mapping, and searching using Firecrawl API.

**Commands:**
- **Scrape a page:** Just send a URL like "https://example.com"
- **Map URLs:** "map https://example.com" or "get links from https://example.com"
- **Search web:** "search for 'your query'" or "find 'machine learning'"
- **Crawl site:** "crawl https://example.com"
- **Check crawl:** "crawl status <job_id>"

**Advanced options:**
- Scrape with formats: URLs automatically detect format requests
- Map with search: "map https://example.com containing 'blog'"
- Debug: "debug on/off/status"

**Available formats:** markdown, html, rawHtml, screenshot, links, json

Example: "https://example.com screenshot" to get a screenshot."""

        except Exception as e:
            error_msg = f"❌ Error during operation: {str(e)}"
            logger.error(error_msg)

            if self.valves.DEBUG_MODE:
                logger.error(traceback.format_exc())
                return f"{error_msg}\n\n🔧 Debug traceback:\n{traceback.format_exc()}"

            return error_msg
