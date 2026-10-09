"""Literature data providers (academic papers, quant blogs)."""

from quantlab.data.literature.base import LiteratureProvider, ProviderError
from quantlab.data.literature.models import PaperItem

__all__ = [
    "LiteratureProvider",
    "PaperItem",
    "ProviderError",
]
