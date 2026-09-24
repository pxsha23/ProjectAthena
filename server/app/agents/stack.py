from app.agents.base import BaseAgent
from app.schemas.agents import StackAgentInput, StackPlan


class StackAgent(BaseAgent[StackAgentInput, StackPlan]):
    """Chooses frameworks, database and hosting that fit the spec."""

    name = "stack"
    output_model = StackPlan
    instructions = (
        "You are the Tech Stack Agent. Choose a stack that fits the spec and that a student can learn and "
        "deploy for free.\n"
        "- Give one choice per layer that the app needs (frontend, backend, database, auth, hosting).\n"
        "- Each reason must refer to something in the spec.\n"
        "- Prefer well documented, mainstream tools. Offer one or two alternatives per choice.\n"
        "- Fill backendLanguage, frontendFramework, backendFramework and database so they agree with "
        "the choices list."
    )

    def check_output(self, data: StackAgentInput, output: StackPlan) -> None:
        layers = {choice.layer for choice in output.choices}
        if output.frontend_framework != "none" and "frontend" not in layers:
            raise ValueError("frontendFramework is set but there is no frontend choice.")
        if output.backend_framework != "none" and "backend" not in layers:
            raise ValueError("backendFramework is set but there is no backend choice.")
        if output.database != "none" and "database" not in layers:
            raise ValueError("database is set but there is no database choice.")
