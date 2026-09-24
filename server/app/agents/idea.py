from app.agents.base import BaseAgent
from app.schemas.agents import IdeaAgentInput, ProjectSpec


class IdeaAgent(BaseAgent[IdeaAgentInput, ProjectSpec]):
    """Brainstorms with the user's idea and writes the project spec."""

    name = "idea"
    output_model = ProjectSpec
    instructions = (
        "You are the Idea Agent. Turn the user's app idea into a clear, realistic spec for a first version "
        "that a student can build.\n"
        "- summary: two or three sentences on what the app does and who it helps.\n"
        "- targetUsers: the distinct groups of people who will use it.\n"
        '- sections: always include "Core features" (3 to 7 concrete, testable features), '
        '"Non-functional requirements", and "Out of scope (v1)".\n'
        "- openQuestions: assumptions you made that the user should confirm.\n"
        "Keep the scope small enough for a final year project."
    )

    def check_output(self, data: IdeaAgentInput, output: ProjectSpec) -> None:
        if not any(section.title.lower().startswith("core features") for section in output.sections):
            raise ValueError('The spec must contain a section titled "Core features".')
