"""Literature data providers (academic papers, quant blogs)."""

from quantlab.data.literature.base import LiteratureProvider, ProviderError
from quantlab.data.literature.blogs import QuantBlogProvider
from quantlab.data.literature.models import PaperItem
from quantlab.data.literature.papers import AcademicPapersProvider

__all__ = [
    "AcademicPapersProvider",
    "LiteratureProvider",
    "PaperItem",
    "ProviderError",
    "QuantBlogProvider",
]
