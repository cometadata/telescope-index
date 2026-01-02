"""Software URL extractor for relatedIdentifiers."""

from typing import Any

from .base import RelatedIdentifierExtractor
from .patterns.software import is_software_url


class SoftwareExtractor(RelatedIdentifierExtractor):
    """Extract software URLs from relatedIdentifiers.

    Handles two relation types:
    - IsSupplementedBy: Primary software implementation (stored as single URL)
    - References: Software mentioned in text (stored as list)

    Both contribute to has_software boolean flag.
    """

    @property
    def relation_types(self) -> set[str]:
        """Return relation types for software."""
        return {"IsSupplementedBy", "References"}

    def matches(self, url: str) -> bool:
        """Check if URL matches software patterns."""
        return is_software_url(url)

    def extract(self, record: dict) -> dict[str, Any]:
        """Extract software URLs from a DataCite record.

        Args:
            record: A DataCite record dictionary.

        Returns:
            Dictionary with:
            - software_repository: str (first IsSupplementedBy URL, or empty)
            - software_references: list[str] (all References URLs)
            - has_software: bool (True if any software URLs found)
            - has_software_repository: bool (True if software_repository exists)
            - has_software_references: bool (True if software_references exist)
        """
        related_identifiers = self._get_related_identifiers(record)

        software_repository = ""
        software_references: list[str] = []

        for identifier in related_identifiers:
            if identifier.get("relatedIdentifierType") != "URL":
                continue

            relation_type = identifier.get("relationType", "")
            if relation_type not in self.relation_types:
                continue

            url = identifier.get("relatedIdentifier", "")
            if not url or not self.matches(url):
                continue

            if relation_type == "IsSupplementedBy":
                if not software_repository:
                    software_repository = url
            elif relation_type == "References":
                software_references.append(url)

        has_software = bool(software_repository or software_references)

        return {
            "software_repository": software_repository,
            "software_references": software_references,
            "has_software": has_software,
            "has_software_repository": bool(software_repository),
            "has_software_references": bool(software_references),
        }
