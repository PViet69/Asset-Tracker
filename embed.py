from openai import OpenAI


def get_embedding(text, base_url, api_key=None, model="text-embedding-3-small"):
    """Get embedding vector for a single text.

    Args:
        text: Input text string.
        base_url: Custom endpoint URL (e.g. "http://localhost:11434/v1").
        api_key: Optional API key. Defaults to "not-needed" for keyless endpoints.
        model: Model name to use for embedding.

    Returns:
        List[float]: The embedding vector.
    """
    client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
    response = client.embeddings.create(model=model, input=text)
    return response.data[0].embedding


def get_embeddings(texts, base_url, api_key=None, model="text-embedding-3-small"):
    """Get embedding vectors for multiple texts.

    Args:
        texts: List of input text strings.
        base_url: Custom endpoint URL (e.g. "http://localhost:11434/v1").
        api_key: Optional API key. Defaults to "not-needed" for keyless endpoints.
        model: Model name to use for embedding.

    Returns:
        List[List[float]]: List of embedding vectors.
    """
    client = OpenAI(base_url=base_url, api_key=api_key or "not-needed")
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]
