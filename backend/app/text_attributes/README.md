# Text Attributes — Heuristic Inference

Keyword/rule-based inference of venue attributes from review snippets. No ML dependencies.

## Public API

```python
from app.text_attributes import infer_attributes_from_text

scores, evidence = infer_attributes_from_text([
    "Quiet cafe with great wifi.",
    "Fast service and good value.",
])
```

## Canonical attributes

| Key | Positive signal examples | Negative signal examples |
|-----|-------------------------|------------------------|
| `quiet` | quiet, peaceful, calm | loud, noisy, crowded |
| `noisy` | loud, rowdy, packed | quiet, peaceful, calm |
| `laptop_friendly` | wifi, outlets, laptop | no wifi, no outlets |
| `romantic` | romantic, date night, cozy | sports bar, rowdy |
| `fast_service` | fast service, no wait | slow service, long wait |
| `value` | good value, affordable | overpriced, not worth |

## Scoring

Per attribute: `score = pos_count / (pos_count + neg_count + 1)`

- Attributes with **no** positive or negative matches are omitted from the output.
- Negation snippets (e.g. "no wifi") suppress positive hits for that snippet.
- Up to 3 evidence snippets per attribute (truncated to 160 chars).

## Upgrade path

Replace the body of `infer_attributes_from_text` with an ML classifier while keeping the same return shape. `VenueProfile` remains the storage layer.
