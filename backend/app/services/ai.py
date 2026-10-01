"""What every AI feature shares: the Claude client, the model, and turning API
problems into messages the cook can read.

Used by ingredient recognition (ingredient_ai.py) and the substitution
assistant (substitute_ai.py). Every AI feature only suggests: nothing is saved
until the user confirms, and the app works normally without an API key.
"""
import logging

import anthropic

from app.config import ANTHROPIC_API_KEY

logger = logging.getLogger("sliced")

MODEL = "claude-opus-5"


class AIError(Exception):
    """The AI couldn't give an answer. The message is safe to show the user."""


def is_available() -> bool:
    return ANTHROPIC_API_KEY is not None


def _client() -> anthropic.Anthropic:
    # Short timeout: the user is waiting on a page. One retry covers a brief hiccup.
    return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=30.0, max_retries=1)


def ask(system: str, content: str, output_format, no_answer_message: str, effort: str = "low"):
    """Send one question and get back an `output_format` object, or raise AIError."""
    try:
        response = _client().beta.messages.parse(
            model=MODEL,
            max_tokens=2048,
            output_config={"effort": effort},
            # If a safety check declines the request, let the API retry it on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": content}],
            # The SDK warns this is deprecated in favor of output_config.format, but in this
            # SDK version (0.x, the last to support Python 3.9) it's the only way to get a
            # parsed Pydantic object back from the beta endpoint that fallbacks need.
            output_format=output_format,
        )
    except anthropic.AuthenticationError:
        logger.error("Anthropic API key was rejected")
        raise AIError("The AI key in .env was rejected. Check ANTHROPIC_API_KEY.")
    except anthropic.RateLimitError:
        raise AIError("The AI is busy right now. Try again in a minute.")
    except anthropic.APIConnectionError:
        raise AIError("Couldn't reach the AI. Check your internet connection.")
    except anthropic.APIStatusError as error:
        logger.error("Anthropic API error %s: %s", error.status_code, error.message)
        raise AIError("The AI had a problem answering. Try again later.")

    if response.stop_reason == "refusal" or response.parsed_output is None:
        logger.warning("No AI answer (stop_reason=%s)", response.stop_reason)
        raise AIError(no_answer_message)
    return response.parsed_output
