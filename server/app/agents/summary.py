from app.agents.base import BaseAgent
from app.schemas.agents import LearningSummary, SummaryAgentInput


class SummaryAgent(BaseAgent[SummaryAgentInput, LearningSummary]):
    """Writes the long, detailed learning summary of everything that was built."""

    name = "summary"
    output_model = LearningSummary
    instructions = (
        "You are the Summary Agent. Write a long, detailed learning summary that teaches a student how "
        "their generated project works, so they can explain it in their report and viva.\n"
        "- overview.summary: two or three paragraphs describing what was built and how the parts connect.\n"
        "- overview.nextSteps: concrete improvements, including fixes for any EVA failures.\n"
        "- topics: 6 to 8 topics in reading order, from architecture down to deployment. For each: "
        "a plain-words explanation, the key concepts, step-by-step how it works in THIS project, "
        "the files to read (only paths from filePaths), key terms with meanings, and a small exercise.\n"
        "- Refer to real file names, routes and functions from the project. Avoid generic filler."
    )

    def check_output(self, data: SummaryAgentInput, output: LearningSummary) -> None:
        known = set(data.file_paths)
        unknown = sorted({path for topic in output.topics for path in topic.files} - known)
        if unknown:
            raise ValueError(f"topics reference files that do not exist in filePaths: {unknown}")
