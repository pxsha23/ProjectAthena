from app.agents.base import BaseAgent
from app.schemas.agents import ChatAgentInput, ChatAgentOutput

PERSONAS = {
    "idea": "the Idea Agent, a product thinker who owns the spec",
    "stack": "the Tech Stack Agent, an architect who owns the technology choices",
    "code": "the Code Agent, an engineer who owns the source code",
    "deploy": "the Deployment & Summary Agent, who owns deployment files and the learning summary",
    "eva": "EVA, who simulates virtual users (codenamed Alpha, Bravo, Charlie) to test usability",
}


class ChatAgent(BaseAgent[ChatAgentInput, ChatAgentOutput]):
    """Answers the user's questions in the workspace chat, speaking as the selected agent."""

    name = "chat"
    output_model = ChatAgentOutput
    instructions = (
        "You answer questions from the student in the project workspace chat. The input says which agent "
        "you are speaking as; stay in that role. Use the project context to give specific answers that "
        "refer to real files and decisions. Keep replies short: a few sentences."
    )

    def build_prompt(self, data: ChatAgentInput) -> str:
        return f"You are speaking as {PERSONAS[data.agent]}.\n\n{super().build_prompt(data)}"
