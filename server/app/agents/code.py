from app.agents.base import BaseAgent
from app.schemas.agents import CodeAgentInput, CodeBundle


class CodeAgent(BaseAgent[CodeAgentInput, CodeBundle]):
    """Generates the project files for the chosen stack."""

    name = "code"
    output_model = CodeBundle
    instructions = (
        "You are the Code Agent. Generate a small, working first version of the app described by the spec, "
        "using exactly the chosen stack.\n"
        "- Put the backend under backend/ and the frontend under frontend/ when both exist.\n"
        "- Include dependency manifests: backend/requirements.txt for Python, "
        "frontend/package.json for Node.\n"
        "- Every third-party import must be listed in the matching manifest and in dependencies.\n"
        "- Include a README.md explaining how to run the project.\n"
        "- Keep files short and readable, with brief comments where a student might be confused.\n"
        "- Do not include deployment files (Dockerfile, CI workflows); another agent writes those.\n"
        "- Paths are relative POSIX paths with no leading slash."
    )

    def check_output(self, data: CodeAgentInput, output: CodeBundle) -> None:
        paths = {f.path for f in output.files}
        missing = [p for p in output.entrypoints if p not in paths]
        if missing:
            raise ValueError(f"entrypoints refer to files that were not generated: {missing}")
