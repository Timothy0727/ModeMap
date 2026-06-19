"""Text attribute inference for venues. See heuristics.py for design."""

from app.text_attributes.heuristics import ATTRIBUTE_RULES, infer_attributes_from_text

__all__ = ["ATTRIBUTE_RULES", "infer_attributes_from_text"]
