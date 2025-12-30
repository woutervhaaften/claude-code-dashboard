"""Insights package for deep Claude Code usage analysis.

Provides analyzers for:
- Tool/MCP usage and costs
- Cache efficiency
- Skill performance
- Anomaly detection (loops, spikes)
- Usage prediction
- ROI analysis
"""

from .tool_analyzer import ToolAnalyzer
from .cache_analyzer import CacheAnalyzer
from .anomaly_detector import AnomalyDetector
from .skill_analyzer import SkillAnalyzer
from .predictor import UsagePredictor
from .roi_analyzer import ROIAnalyzer
from .report import InsightsReport

__all__ = [
    "ToolAnalyzer",
    "CacheAnalyzer",
    "AnomalyDetector",
    "SkillAnalyzer",
    "UsagePredictor",
    "ROIAnalyzer",
    "InsightsReport",
]
