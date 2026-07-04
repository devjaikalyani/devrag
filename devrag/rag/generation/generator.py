"""
generator.py
------------
LLM answer generation for the RAG pipeline, backed by the unified DevRAG
LLM client (Claude Sonnet 5 by default, with provider fallbacks).

  - Streaming support
  - System prompt tuned for code Q&A with citations
  - Conversation history support
"""

from typing import Generator, List, Optional

from loguru import logger

from devrag.llm.client import chat, stream_chat


SYSTEM_PROMPT = """You are DevRAG, an expert AI assistant for understanding any codebase.

You MUST format ALL responses using proper markdown. Follow these rules exactly:

FORMATTING (mandatory):
- Start bullet points on their OWN LINE with "- " (dash space)
- Put a BLANK LINE before and after every bullet list
- Put a BLANK LINE before and after every heading
- Use ### for section headings on their own line
- Use **bold** for key terms and file names
- Use `backticks` for code, functions, variables, file names
- Use fenced code blocks (```language) for multi-line code
- NEVER run bullets into a paragraph — each bullet must be on its own line

CONTENT RULES:
1. Only use information from the retrieved code context
2. Always cite source files: "According to `filename`..."
3. For overview questions use this structure:
   - One sentence summary
   - Blank line
   - ### Tech Stack (bullet list)
   - ### Features (bullet list)
   - ### Structure (bullet list)
4. Show actual code snippets for code questions
5. Never hallucinate APIs or code not in the context
"""


class AnswerGenerator:
    """Generates cited answers from retrieved code context."""

    def __init__(self, model: Optional[str] = None):
        self.model = model
        logger.info(f"Answer generator initialized (model={model or 'default'})")

    def _build_messages(
        self,
        query: str,
        context: str,
        history: Optional[List[dict]] = None,
    ) -> List[dict]:
        messages: List[dict] = []
        if history:
            messages.extend(history[-6:])  # last 3 turns

        user_content = (
            f"## Retrieved Code Context\n\n{context}\n\n"
            f"---\n\n"
            f"## Question\n\n{query}"
        )
        messages.append({"role": "user", "content": user_content})
        return messages

    def generate(
        self,
        query: str,
        context: str,
        history: Optional[List[dict]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> str:
        """Non-streaming generation. Returns full response string."""
        messages = self._build_messages(query, context, history)
        msg, _ = chat(messages, system=SYSTEM_PROMPT, max_tokens=max_tokens, model=self.model)
        answer = msg.content or ""
        logger.debug(f"Generated {len(answer)} chars")
        return answer

    def stream(
        self,
        query: str,
        context: str,
        history: Optional[List[dict]] = None,
        max_tokens: int = 2048,
        temperature: float = 0.0,
    ) -> Generator[str, None, None]:
        """Streaming generation. Yields text chunks as they arrive."""
        messages = self._build_messages(query, context, history)
        yield from stream_chat(messages, system=SYSTEM_PROMPT, max_tokens=max_tokens, model=self.model)


# Backwards-compatible alias for code written against the Groq generator
GroqGenerator = AnswerGenerator
