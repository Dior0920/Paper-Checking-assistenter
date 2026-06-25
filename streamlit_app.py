"""
论文检索助手 - Streamlit 界面

一个简单的学术论文搜索工具，支持：
- 搜索 ArXiv 论文
- AI 总结论文内容
- 英文摘要翻译成中文
"""

import os
import re
import streamlit as st
from dotenv import load_dotenv

# 加载 .env 中的环境变量（使用显式路径确保在任何工作目录下都能正确加载）
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(env_path)

# 导入我们的自定义工具
from minimal_agent.tools import ArxivSearchTool, SummarizeTool, TranslateTool

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="论文检索助手",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# 初始化工具（只创建一次，缓存起来）
# ============================================================
@st.cache_resource
def get_tools():
    """创建并缓存工具实例，避免每次刷新都重新创建"""
    return {
        "search": ArxivSearchTool(max_results=5),
        "summarize": SummarizeTool(),
        "translate": TranslateTool(),
    }


tools = get_tools()


# ============================================================
# 解析函数：把 ArXiv 搜索返回的文本解析成论文列表
# ============================================================
def parse_results(text: str) -> list[dict]:
    """将 search_arxiv 返回的格式化文本解析为结构化的论文列表"""
    papers = []
    # 如果是错误信息或未找到，直接返回空列表
    if "未找到" in text or "出错" in text:
        return papers

    # 按分隔符拆分每篇论文
    parts = text.split("\n\n---\n\n")
    for part in parts:
        # 跳过标题头部分
        if part.startswith("## ArXiv 搜索结果") or not part.strip():
            continue

        paper = {}
        lines = part.split("\n")
        for line in lines:
            line = line.strip()
            if line.startswith("### ") and "." in line[:8]:
                # 标题行: "### 1. Paper Title"
                title_part = line.split(". ", 1)
                paper["title"] = title_part[1] if len(title_part) > 1 else line[4:]
            elif line.startswith("**作者**:"):
                paper["authors"] = line.replace("**作者**:", "").strip()
            elif line.startswith("**发表时间**:"):
                paper["published"] = line.replace("**发表时间**:", "").strip()
            elif line.startswith("**ArXiv ID**:"):
                paper["arxiv_id"] = line.replace("**ArXiv ID**:", "").strip()
            elif line.startswith("**摘要**:"):
                paper["abstract"] = line.replace("**摘要**:", "").strip()
            elif line.startswith("**链接**:"):
                links_part = line.replace("**链接**:", "").strip()
                abs_match = re.search(r"\[摘要页\]\(([^)]+)\)", links_part)
                pdf_match = re.search(r"\[PDF\]\(([^)]+)\)", links_part)
                if abs_match:
                    paper["abs_url"] = abs_match.group(1)
                if pdf_match:
                    paper["pdf_url"] = pdf_match.group(1)

        if paper.get("title"):
            papers.append(paper)

    return papers


# ============================================================
# 初始化 Session State（保存状态，避免重复操作）
# ============================================================
if "papers" not in st.session_state:
    st.session_state.papers = []          # 保存搜索结果
if "summaries" not in st.session_state:
    st.session_state.summaries = {}       # 保存每篇论文的总结 {index: summary_text}
if "translations" not in st.session_state:
    st.session_state.translations = {}    # 保存每篇论文的翻译 {index: translation_text}
if "last_query" not in st.session_state:
    st.session_state.last_query = ""      # 上次搜索的关键词

# ============================================================
# 侧边栏
# ============================================================
with st.sidebar:
    st.title("📚 论文检索助手")
    st.markdown("---")
    st.markdown("""
    ### 功能说明

    1. **搜索论文** — 输入关键词，从 ArXiv 搜索相关学术论文
    2. **AI 总结** — 用 AI 帮你总结论文的核心内容
    3. **中文翻译** — 把英文摘要翻译成自然流畅的中文

    ### 使用提示

    - 关键词越具体，结果越精准
    - 可以使用英文或中文关键词
    - 例如：`large language model`、`大语言模型`、`retrieval augmented generation`
    """)

    st.markdown("---")
    st.markdown("### ⚙️ 设置")
    max_results = st.slider("搜索结果数量", min_value=1, max_value=10, value=5)

    st.markdown("---")
    st.caption("Powered by ArXiv API + DeepSeek LLM")

# ============================================================
# 主界面
# ============================================================
st.title("📚 论文检索助手")
st.markdown("*用 AI 帮你搜索、理解和翻译学术论文*")

# --- 搜索栏 ---
col1, col2 = st.columns([4, 1])
with col1:
    query = st.text_input(
        "输入搜索关键词",
        placeholder="例如: large language model, retrieval augmented generation, 大语言模型...",
        label_visibility="collapsed",
        key="search_input",
    )
with col2:
    search_btn = st.button("🔍 搜索论文", type="primary", use_container_width=True)

# ============================================================
# 执行搜索
# ============================================================
if search_btn and query.strip():
    st.session_state.last_query = query.strip()
    st.session_state.summaries = {}       # 新的搜索，清空旧的总结
    st.session_state.translations = {}    # 新的搜索，清空旧的翻译

    with st.spinner(f"正在 ArXiv 上搜索: **{query}** ..."):
        tools["search"].max_results = max_results
        result_text = tools["search"](query=query.strip(), max_results=max_results)

    # 解析搜索结果为结构化数据
    st.session_state.papers = parse_results(result_text)

    if not st.session_state.papers:
        st.warning(f"未找到与 **{query}** 相关的论文，请尝试其他关键词。")

# ============================================================
# 显示搜索结果
# ============================================================
if st.session_state.papers:
    st.markdown(f"### 🔍 搜索结果: \"{st.session_state.last_query}\"")
    st.markdown(f"共找到 **{len(st.session_state.papers)}** 篇论文")
    st.markdown("---")

    for i, paper in enumerate(st.session_state.papers):
        # 为每篇论文创建一个卡片区域
        with st.container():
            # 标题行 + 操作按钮
            col1, col2, col3 = st.columns([6, 1, 1])

            with col1:
                st.markdown(f"#### 📄 {i+1}. {paper.get('title', '未知标题')}")

            with col2:
                summarize_key = f"summarize_{i}"
                if st.button("🤖 AI 总结", key=summarize_key, use_container_width=True):
                    with st.spinner("AI 正在生成中文总结..."):
                        abstract = paper.get("abstract", "")
                        if abstract:
                            try:
                                summary = tools["summarize"](
                                    title=paper.get("title", ""),
                                    abstract=abstract,
                                )
                                st.session_state.summaries[i] = summary
                            except Exception as e:
                                st.session_state.summaries[i] = f"❌ 总结生成失败: {str(e)}"
                        else:
                            st.session_state.summaries[i] = "⚠️ 该论文没有摘要信息，无法生成总结。"

            with col3:
                translate_key = f"translate_{i}"
                if st.button("🌐 翻译摘要", key=translate_key, use_container_width=True):
                    with st.spinner("正在翻译成中文..."):
                        abstract = paper.get("abstract", "")
                        if abstract:
                            try:
                                translation = tools["translate"](text=abstract)
                                st.session_state.translations[i] = translation
                            except Exception as e:
                                st.session_state.translations[i] = f"❌ 翻译失败: {str(e)}"
                        else:
                            st.session_state.translations[i] = "⚠️ 该论文没有摘要信息，无法翻译。"

            # 论文基本信息
            st.markdown(f"**作者**: {paper.get('authors', '未知')}")
            st.markdown(f"**发表时间**: {paper.get('published', '未知')}")

            # 原始摘要（可折叠）
            with st.expander("📝 查看原始摘要"):
                st.markdown(paper.get("abstract", "无摘要"))

            # ArXiv 链接
            abs_url = paper.get("abs_url", "")
            pdf_url = paper.get("pdf_url", "")
            if abs_url or pdf_url:
                links = []
                if abs_url:
                    links.append(f"[📄 摘要页]({abs_url})")
                if pdf_url:
                    links.append(f"[📥 下载 PDF]({pdf_url})")
                st.markdown(" | ".join(links))

            # 显示 AI 总结结果
            if i in st.session_state.summaries:
                st.markdown("---")
                st.markdown("#### 🤖 AI 总结")
                st.success(st.session_state.summaries[i])

            # 显示翻译结果
            if i in st.session_state.translations:
                st.markdown("---")
                st.markdown("#### 🌐 中文翻译")
                st.info(st.session_state.translations[i])

            st.markdown("---")

# ============================================================
# 初始状态提示（首次打开，还没有搜索时显示）
# ============================================================
elif not st.session_state.papers and not search_btn:
    st.markdown("""
    ---
    ### 👋 欢迎使用论文检索助手！

    在搜索框中输入你感兴趣的研究领域关键词，然后点击 **搜索论文** 按钮开始探索。

    **热门搜索建议**:
    - `Retrieval Augmented Generation` — RAG 检索增强生成
    - `Large Language Model Alignment` — 大模型对齐
    - `Multi-Agent Reinforcement Learning` — 多智能体强化学习
    """)
