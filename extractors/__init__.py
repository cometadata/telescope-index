"""Extractors for processing relatedIdentifiers from DataCite records."""

from .base import RelatedIdentifierExtractor
from .software import SoftwareExtractor

__all__ = ["RelatedIdentifierExtractor", "SoftwareExtractor"]
