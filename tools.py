class FinalAnswerTool:
    name = "final_answer"
    description = "Provides a final answer to the given problem."
    inputs = {
        "answer": {"type": "any", "description": "The final answer to the problem"}
    }
    output_type = "any"

    def __call__(self, answer):
        return answer


class VisitWebpageTool:
    name = "visit_webpage"
    description = "Visits a webpage at the given url and reads its content as a markdown string. Use this to browse webpages."
    inputs = {
        "url": {
            "type": "string",
            "description": "The url of the webpage to visit.",
        }
    }
    output_type = "string"

    def __init__(self, max_output_length: int = 40000):
        super().__init__()
        self.max_output_length = max_output_length

    def __call__(self, url: str) -> str:
        try:
            import re

            import requests
            from markdownify import markdownify
            from requests.exceptions import RequestException
            from smolagents.utils import truncate_content
        except ImportError as e:
            raise ImportError(
                "You must install packages `markdownify` and `requests` to run this tool: for instance run `pip install markdownify requests`."
            ) from e
        try:
            # Send a GET request to the URL with a 20-second timeout
            response = requests.get(url, timeout=20)
            response.raise_for_status()  # Raise an exception for bad status codes

            # Convert the HTML content to Markdown
            markdown_content = markdownify(response.text).strip()

            # Remove multiple line breaks
            markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)

            return truncate_content(markdown_content, self.max_output_length)

        except requests.exceptions.Timeout:
            return "The request timed out. Please try again later or check the URL."
        except RequestException as e:
            return f"Error fetching the webpage: {str(e)}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"


class DuckDuckGoSearchTool:
    name = "web_search"
    description = """Performs a duckduckgo web search based on your query (think a Google search) then returns the top search results."""
    inputs = {
        "query": {"type": "string", "description": "The search query to perform."}
    }
    output_type = "string"

    def __init__(self, max_results=10, **kwargs):
        super().__init__()
        self.max_results = max_results
        try:
            from ddgs import DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS
            except ImportError as e:
                raise ImportError(
                    "You must install `ddgs` to run this tool: pip install ddgs"
                ) from e
        self.ddgs = DDGS(**kwargs)

    def __call__(self, query: str) -> str:
        import time
        max_retries = 3
        for attempt in range(max_retries):
            try:
                results = self.ddgs.text(query, max_results=self.max_results)
                if results and len(results) > 0:
                    postprocessed_results = [
                        f"[{result['title']}]({result['href']})\n{result['body']}"
                        for result in results
                    ]
                    return "## Search Results\n\n" + "\n\n".join(postprocessed_results)
            except Exception:
                pass
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        return "No search results found (DuckDuckGo rate limited). Try a shorter query or use TavilySearchTool instead."

class ArxivSearchTool:
    name = "search_arxiv"
    description = "Searches ArXiv for academic papers matching the given keyword query. Returns paper titles, authors, abstracts, and links."
    inputs = {
        "query": {"type": "string", "description": "The search keyword(s) to find papers on ArXiv."},
        "max_results": {"type": "integer", "description": "Maximum number of results to return (default 5).", "default": 5, "nullable": True},
    }
    output_type = "string"

    def __init__(self, max_results: int = 5):
        super().__init__()
        self.max_results = max_results

    def __call__(self, query: str, max_results: int | None = None) -> str:
        import urllib.parse
        import xml.etree.ElementTree as ET

        import requests

        if max_results is None:
            max_results = self.max_results

        try:
            encoded_query = urllib.parse.quote(query)
            url = f"http://export.arxiv.org/api/query?search_query=all:{encoded_query}&start=0&max_results={max_results}&sortBy=relevance&sortOrder=descending"
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # ArXiv API 返回 Atom XML 格式，需要解析
            root = ET.fromstring(response.text)
            ns = {"atom": "http://www.w3.org/2005/Atom",
                  "arxiv": "http://arxiv.org/schemas/atom"}

            entries = root.findall("atom:entry", ns)
            if not entries:
                return f"未找到与 '{query}' 相关的论文。请尝试其他关键词。"

            results = []
            for i, entry in enumerate(entries, 1):
                title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
                summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")

                authors = entry.findall("atom:author", ns)
                author_names = [author.find("atom:name", ns).text for author in authors]
                authors_str = ", ".join(author_names)

                published = entry.find("atom:published", ns).text[:10]  # 只取日期部分
                arxiv_id = entry.find("atom:id", ns).text.split("/abs/")[-1]
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
                abs_url = f"https://arxiv.org/abs/{arxiv_id}"

                results.append(
                    f"### {i}. {title}\n\n"
                    f"**作者**: {authors_str}\n\n"
                    f"**发表时间**: {published}\n\n"
                    f"**ArXiv ID**: {arxiv_id}\n\n"
                    f"**摘要**: {summary[:500]}{'...' if len(summary) > 500 else ''}\n\n"
                    f"**链接**: [摘要页]({abs_url}) | [PDF]({pdf_url})"
                )

            header = f"## ArXiv 搜索结果: \"{query}\"\n\n找到 {len(entries)} 篇论文:\n\n---\n\n"
            return header + "\n\n---\n\n".join(results)

        except requests.exceptions.Timeout:
            return "ArXiv API 请求超时，请稍后重试。"
        except requests.exceptions.RequestException as e:
            return f"请求 ArXiv API 时出错: {str(e)}"
        except ET.ParseError as e:
            return f"解析 ArXiv 返回数据时出错: {str(e)}"
        except Exception as e:
            return f"搜索 ArXiv 时发生未知错误: {str(e)}"


class SummarizeTool:
    name = "summarize_paper"
    description = "Uses the LLM to generate a concise Chinese summary of an academic paper based on its title and abstract."
    inputs = {
        "title": {"type": "string", "description": "The title of the paper."},
        "abstract": {"type": "string", "description": "The abstract of the paper in English."},
    }
    output_type = "string"

    def __init__(self, model: str | None = None):
        super().__init__()
        import os
        self.model = model or os.environ.get("MODEL", "deepseek/deepseek-chat")

    def __call__(self, title: str, abstract: str) -> str:
        import os

        from litellm import completion

        prompt = f"""你是一位资深的学术论文评审专家。请用通俗易懂的中文，为以下论文写一段简洁的总结（200-300字），让非专业人士也能理解论文的核心内容。

总结请包含以下要点：
1. 这篇论文要解决什么问题？
2. 用了什么方法？
3. 主要发现或结论是什么？

论文标题：{title}
论文摘要：{abstract}

请直接输出中文总结，不要加"这篇论文"开头，直接说内容。"""

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=1024,
            )
            summary = response.choices[0].message.content
            return summary.strip()
        except Exception as e:
            return f"生成总结时出错: {str(e)}"


class TranslateTool:
    name = "translate_to_chinese"
    description = "Translates English text (e.g., paper abstracts) into natural, fluent Chinese."
    inputs = {
        "text": {"type": "string", "description": "The English text to translate into Chinese."},
    }
    output_type = "string"

    def __init__(self, model: str | None = None):
        super().__init__()
        import os
        self.model = model or os.environ.get("MODEL", "deepseek/deepseek-chat")

    def __call__(self, text: str) -> str:
        from litellm import completion

        prompt = f"""你是一位专业的学术翻译。请将以下英文文本翻译成流畅、准确的中文。要求：
- 学术术语翻译准确
- 语句通顺自然，符合中文表达习惯
- 保留原文的所有关键信息

英文原文：
{text}

请直接输出中文翻译："""

        try:
            response = completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                max_tokens=2048,
            )
            translation = response.choices[0].message.content
            return translation.strip()
        except Exception as e:
            return f"翻译时出错: {str(e)}"


class TavilySearchTool:
    name = "tavily_search"
    description = """Performs a Tavily web search based on your query (think a Google search) then returns the top search results."""
    inputs = {
        "query": {"type": "string", "description": "The search query to perform."}
    }
    output_type = "string"

    def __init__(self, max_results=10, **kwargs):
        super().__init__()
        self.max_results = max_results
        try:
            from tavily import TavilyClient
        except ImportError as e:
            raise ImportError(
                "You must install package `tavily` to run this tool: for instance run `pip install tavily`."
            ) from e
        self.tavily = TavilyClient(**kwargs)

    def __call__(self, query: str) -> str:
        import time
        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                results = self.tavily.search(query, max_results=self.max_results)["results"]
                if results and len(results) > 0:
                    postprocessed_results = [
                        f"[{result['title']}]({result['url']})\n{result['content']}"
                        for result in results
                    ]
                    return "## Search Results\n\n" + "\n\n".join(postprocessed_results)
                return "No search results found for the query."
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        return f"Tavily search failed after {max_retries} attempts: {last_error}. Please try a different query."