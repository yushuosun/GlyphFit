"""SWOCR source-aware rendering and measured glyph input selection."""
from .api import candidate_scales, select_measured_candidates, source_render_scale

__all__ = ["source_render_scale", "candidate_scales", "select_measured_candidates"]
