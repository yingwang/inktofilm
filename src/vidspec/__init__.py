"""InkToFilm's backwards-compatible VidSpec evaluation package."""

from vidspec.engine import run_suite
from vidspec.models import RunReport

__all__ = ["RunReport", "run_suite"]
__version__ = "0.4.0"
