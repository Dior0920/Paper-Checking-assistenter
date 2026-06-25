import os

from dotenv import load_dotenv

from minimal_agent.agent import Agent
from minimal_agent.tools import VisitWebpageTool, TavilySearchTool


load_dotenv()


if __name__ == "__main__":
    agent = Agent(
        model=os.environ.get("MODEL"),
        tools=[
            TavilySearchTool(max_results=10),
            VisitWebpageTool(max_output_length=1000),
        ],
        max_steps=15,
    )

    # 可以换成任何你想问的问题
    # 例如: "2025年诺贝尔文学奖得主是谁？"  "iPhone 17有哪些新功能？"
    res = agent.run(
        "2025年英雄联盟全球总决赛冠军是哪支球队？可以给我讲讲Gumayusi的故事吗？"
    )

    print(20 * "-")
    print(f"The final answer is:\n\n{res}")
