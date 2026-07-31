"""
工具执行框架和具体工具实现
"""
from typing import Dict, Any, List, Optional, Callable
from abc import ABC, abstractmethod
import time
import requests
from bs4 import BeautifulSoup
import json


from .base import Tool


class WebSearchTool(Tool):
    """网页搜索工具"""

    def __init__(self, api_key: Optional[str] = None, engine: str = "duckduckgo"):
        """
        初始化搜索工具

        Args:
            api_key: API key（如果使用 SerpAPI 等）
            engine: 搜索引擎（duckduckgo, serpapi, bing）
        """
        self.api_key = api_key
        self.engine = engine

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web for information. Returns a list of search results with titles, URLs, and snippets."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """执行网页搜索"""
        start_time = time.time()

        try:
            if self.engine == "duckduckgo":
                results = self._search_duckduckgo(query)
            else:
                return {
                    "success": False,
                    "output": f"Unsupported search engine: {self.engine}",
                    "raw_output": None,
                    "error": f"Unsupported engine: {self.engine}"
                }

            end_time = time.time()

            # 格式化输出给 LLM
            output_text = f"Search results for '{query}':\n\n"
            for i, result in enumerate(results[:5], 1):
                output_text += f"{i}. {result['title']}\n"
                output_text += f"   URL: {result['url']}\n"
                output_text += f"   {result['snippet']}\n\n"

            return {
                "success": True,
                "output": output_text,
                "raw_output": results,
                "error": None,
                "latency_ms": (end_time - start_time) * 1000
            }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "output": f"Search failed: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (end_time - start_time) * 1000
            }

    def _search_duckduckgo(self, query: str) -> List[Dict[str, str]]:
        """使用 DuckDuckGo 搜索（简单实现）"""
        # 使用 DuckDuckGo HTML 搜索
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        response = requests.post(url, data=params, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        results = []

        for result_div in soup.find_all('div', class_='result')[:10]:
            title_elem = result_div.find('a', class_='result__a')
            snippet_elem = result_div.find('a', class_='result__snippet')

            if title_elem:
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

                results.append({
                    "title": title,
                    "url": url,
                    "snippet": snippet
                })

        return results




class FetchURLTool(Tool):
    """获取网页内容工具"""

    @property
    def name(self) -> str:
        return "fetch_url"

    @property
    def description(self) -> str:
        return "Fetch and extract readable text content from a URL."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch"
                }
            },
            "required": ["url"]
        }

    def execute(self, url: str, **kwargs) -> Dict[str, Any]:
        """获取网页内容"""
        start_time = time.time()

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            # 提取可读文本
            soup = BeautifulSoup(response.text, 'html.parser')

            # 移除 script 和 style 标签
            for script in soup(["script", "style"]):
                script.decompose()

            # 获取文本
            text = soup.get_text()

            # 清理文本
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            # 限制长度
            max_length = 5000
            if len(text) > max_length:
                text = text[:max_length] + "\n\n[Content truncated...]"

            end_time = time.time()

            return {
                "success": True,
                "output": f"Content from {url}:\n\n{text}",
                "raw_output": {"url": url, "text": text, "length": len(text)},
                "error": None,
                "latency_ms": (end_time - start_time) * 1000
            }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "output": f"Failed to fetch {url}: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (end_time - start_time) * 1000
            }




class ExtractInfoTool(Tool):
    """信息提取工具（使用 LLM）"""

    def __init__(self, llm_client):
        """
        初始化提取工具

        Args:
            llm_client: OpenAI 客户端（用于调用 LLM 做提取）
        """
        self.llm_client = llm_client

    @property
    def name(self) -> str:
        return "extract_info"

    @property
    def description(self) -> str:
        return "Extract structured information from text according to a schema."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "The text to extract information from"
                },
                "schema": {
                    "type": "string",
                    "description": "Description of what information to extract (e.g., 'price, date, location')"
                }
            },
            "required": ["text", "schema"]
        }

    def execute(self, text: str, schema: str, **kwargs) -> Dict[str, Any]:
        """提取结构化信息"""
        start_time = time.time()

        try:
            # 使用 LLM 做提取
            prompt = f"""Extract the following information from the text: {schema}

Text:
{text[:2000]}

Return the extracted information as JSON."""

            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",  # 使用更便宜的模型
                messages=[
                    {"role": "system", "content": "You are a helpful information extraction assistant. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )

            extracted = response.choices[0].message.content
            end_time = time.time()

            # 尝试解析 JSON
            try:
                extracted_json = json.loads(extracted)
            except:
                extracted_json = {"raw": extracted}

            return {
                "success": True,
                "output": f"Extracted information:\n{extracted}",
                "raw_output": extracted_json,
                "error": None,
                "latency_ms": (end_time - start_time) * 1000
            }

        except Exception as e:
            end_time = time.time()
            return {
                "success": False,
                "output": f"Extraction failed: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (end_time - start_time) * 1000
            }



