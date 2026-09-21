"""Multilingual E5 embeddings for concept expression retrieval.

The heavyweight model is loaded only by the explicit vector sync / review commands.
The scheduled concept job never downloads a model or performs vector inference.
"""

from __future__ import annotations

from collections.abc import Sequence

MODEL_ID = "intfloat/multilingual-e5-small"
MODEL_REVISION = "fd1525a9fd15316a2d503bf26ab031a61d056e98"
DIMENSIONS = 384


def model_key(model_id: str = MODEL_ID, revision: str = MODEL_REVISION) -> str:
    return f"{model_id}@{revision}"


class E5Encoder:
    def __init__(self, model_id: str = MODEL_ID, revision: str = MODEL_REVISION) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.model_id = model_key(model_id, revision)
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model_id, revision=revision)
        self._model = AutoModel.from_pretrained(model_id, revision=revision)
        self._model.eval()

    def encode(
        self, texts: Sequence[str], *, query: bool, batch_size: int = 32
    ) -> list[list[float]]:
        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        prefix = "query: " if query else "passage: "
        output: list[list[float]] = []
        torch = self._torch
        for offset in range(0, len(texts), batch_size):
            inputs = self._tokenizer(
                [prefix + text for text in texts[offset : offset + batch_size]],
                max_length=512,
                padding=True,
                truncation=True,
                return_tensors="pt",
            )
            with torch.no_grad():
                hidden = self._model(**inputs).last_hidden_state
                mask = inputs["attention_mask"].unsqueeze(-1)
                pooled = (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                normalized = torch.nn.functional.normalize(pooled, p=2, dim=1)
            values = normalized.tolist()
            if any(len(value) != DIMENSIONS for value in values):
                raise ValueError(f"expected {DIMENSIONS}-dimensional embeddings")
            output.extend(values)
        return output
