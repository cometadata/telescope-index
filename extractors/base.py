"""Base class for relatedIdentifier extractors."""

from abc import ABC, abstractmethod
from typing import Any


class RelatedIdentifierExtractor(ABC):
    """Base class for extracting typed data from relatedIdentifiers.

    Subclasses implement extraction logic for specific types of related
    resources (software, datasets, documentation, etc.).
    """

    @property
    @abstractmethod
    def relation_types(self) -> set[str]:
        """Return the relationTypes this extractor handles.

        Returns:
            Set of relationType values (e.g., {"IsSupplementedBy", "References"}).
        """
        pass

    @abstractmethod
    def matches(self, url: str) -> bool:
        """Check if a URL matches this extractor's patterns.

        Args:
            url: The URL to check.

        Returns:
            True if the URL should be processed by this extractor.
        """
        pass

    @abstractmethod
    def extract(self, record: dict) -> dict[str, Any]:
        """Extract fields from a DataCite record.

        Args:
            record: A DataCite record dictionary with 'attributes' containing
                    'relatedIdentifiers'.

        Returns:
            Dictionary of field names to values to add to the index document.
        """
        pass

    def _get_related_identifiers(self, record: dict) -> list[dict]:
        """Helper to get relatedIdentifiers from a record.

        Args:
            record: A DataCite record dictionary.

        Returns:
            List of relatedIdentifier dictionaries.
        """
        return record.get("attributes", {}).get("relatedIdentifiers", []) or []
