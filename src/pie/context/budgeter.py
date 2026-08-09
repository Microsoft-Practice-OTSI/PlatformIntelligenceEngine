"""Token Budgeting and Allocation Engine: Estimates token consumption and enforces
strict token bounds across prompt sections to prevent LLM truncation and cognitive loss.
"""

from pie.context.models import TokenBudget


class TokenBudgeter:
    """Accurately budgets and allocates token limits across context sections."""

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimate token count using BPE character-to-token heuristic (~4 chars per token)."""
        if not text:
            return 0
        return max(1, int(len(text) / 3.8))

    @staticmethod
    def fit_lines_to_budget(lines: list[str], max_tokens: int, section_name: str = "Section") -> str:
        """Fit a list of markdown lines into a maximum token budget, adding a compact summary if truncated."""
        if not lines:
            return "*None recorded.*"

        result_lines: list[str] = []
        current_tokens = 0
        omitted_count = 0

        for idx, line in enumerate(lines):
            line_tokens = TokenBudgeter.estimate_tokens(line + "\n")
            if current_tokens + line_tokens > max_tokens:
                omitted_count = len(lines) - idx
                break
            result_lines.append(line)
            current_tokens += line_tokens

        if omitted_count > 0:
            result_lines.append(f"\n*(... {omitted_count} additional {section_name} items compressed to preserve token budget)*")

        return "\n".join(result_lines)
