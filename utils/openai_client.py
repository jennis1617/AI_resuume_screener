"""
OpenAI Client Initialization
Single API key version
"""

from openai import OpenAI


def init_openai_client(api_key: str):
    """Initialize and return OpenAI client."""
    return OpenAI(api_key=api_key)


def create_openai_completion(client, **kwargs):
    """
    Create a chat completion using the OpenAI client.

    All kwargs are forwarded to:
    client.chat.completions.create()
    """
    return client.chat.completions.create(**kwargs)