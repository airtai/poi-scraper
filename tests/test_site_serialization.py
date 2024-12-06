from pathlib import Path

from poi_scraper.poi_manager import PoiManager
from poi_scraper.statistics import Link, Site

from .test_poi_manager import MockValidatePoiAgent


class TestSiteSerialization:
    """Test suite for verifying Site serialization functionality."""

    def setup_test_site(self, base_url: str) -> Site:
        """Creates a complex website structure for testing serialization.

        This creates a site structure that mimics a travel website with:
        - Homepage linking to main sections
        - Destinations section with multiple countries and cities
        - Hotels section with different properties
        - Cross-links between related pages (e.g., city pages link to their hotels)
        - Circular references (hotels link back to their city pages)
        """
        # Create homepage and primary navigation structure
        homepage = Link.create(parent=None, url=base_url, estimated_score=5)
        homepage.record_visit(
            poi_found=True,
            urls_found={
                "https://travel.example.com/destinations": 5,
                "https://travel.example.com/hotels": 4,
                "https://travel.example.com/about": 2,
            },
        )

        # Create and visit the destinations page with country links
        destinations = homepage.site.urls["https://travel.example.com/destinations"]
        destinations.record_visit(
            poi_found=False,
            urls_found={
                "https://travel.example.com/destinations/france": 5,
                "https://travel.example.com/destinations/italy": 5,
                "https://travel.example.com/destinations/spain": 5,
            },
        )

        # Create and visit country pages with city links
        france = homepage.site.urls["https://travel.example.com/destinations/france"]
        france.record_visit(
            poi_found=True,
            urls_found={
                "https://travel.example.com/destinations/france/paris": 5,
                "https://travel.example.com/destinations/france/nice": 4,
            },
        )

        # Create and visit city pages with attraction links
        paris = homepage.site.urls[
            "https://travel.example.com/destinations/france/paris"
        ]
        paris.record_visit(
            poi_found=True,
            urls_found={
                "https://travel.example.com/hotels/paris-grand": 4,
                "https://travel.example.com/hotels/paris-boutique": 4,
            },
        )

        # Create and visit hotels section with cross-links
        hotels = homepage.site.urls["https://travel.example.com/hotels"]
        hotels.record_visit(
            poi_found=False,
            urls_found={
                "https://travel.example.com/hotels/paris-grand": 4,
                "https://travel.example.com/hotels/paris-boutique": 4,
                "https://travel.example.com/hotels/nice-resort": 3,
            },
        )

        # Create hotel pages that link back to their city pages
        paris_grand = homepage.site.urls[
            "https://travel.example.com/hotels/paris-grand"
        ]
        paris_grand.record_visit(
            poi_found=True,
            urls_found={
                "https://travel.example.com/destinations/france/paris": 5  # Circular reference
            },
        )

        return homepage.site

    def verify_site_reconstruction(
        self, original_site: Site, reconstructed_site: Site
    ) -> None:
        """Verifies that the site was reconstructed correctly with all its properties and relationships.

        This method checks that:
        1. All pages exist in the reconstructed site
        2. All link properties are preserved
        3. All relationships (parents/children) are maintained
        4. Circular references are handled correctly
        """
        for url, original_link in original_site.urls.items():
            reconstructed_link = reconstructed_site.urls[url]

            # Verify basic properties
            assert reconstructed_link.url == original_link.url
            assert reconstructed_link.estimated_score == original_link.estimated_score
            assert reconstructed_link.visited == original_link.visited
            assert reconstructed_link.score == original_link.score
            assert reconstructed_link.children_visited == original_link.children_visited
            assert (
                reconstructed_link.children_poi_found
                == original_link.children_poi_found
            )

            # Verify relationships
            original_parent_urls = {p.url for p in original_link.parents}
            reconstructed_parent_urls = (
                set()
                if reconstructed_link.parents is None
                else {p.url for p in reconstructed_link.parents}
            )
            assert reconstructed_parent_urls == original_parent_urls

            original_child_urls = {c.url for c in original_link.children}
            reconstructed_child_urls = {c.url for c in reconstructed_link.children}
            assert reconstructed_child_urls == original_child_urls

    def test_site_serialization_with_file(self) -> None:
        """Tests that our Site serialization works correctly with a complex website structure.

        This test creates a realistic website structure with multiple levels of pages,
        cross-references, and circular links, then verifies that all this complexity
        is preserved through the serialization process.
        """
        db_path = Path("test_poi_data.db")
        base_url = "https://travel.example.com"
        workflow_name = "Test Workflow"
        try:
            # Create our complex test site
            original_site = self.setup_test_site(base_url)

            # Create manager with explicit db path
            manager = PoiManager(
                base_url=base_url,
                poi_validator=MockValidatePoiAgent(),
                workflow_name=workflow_name,
                db_path=db_path,
            )
            # save the state in the database
            manager.homepage = original_site.urls[base_url]
            manager._save_state_in_db()

            # resume workflow
            manager.workflow_id, site_obj = manager.db.create_or_get_workflow(
                workflow_name, base_url
            )

            # Verify the reconstruction
            if site_obj:
                reconstructed_site = site_obj.site_obj
                self.verify_site_reconstruction(original_site, reconstructed_site)
            else:
                raise ValueError("Site object not found in database.")

        finally:
            # Clean up
            if db_path.exists():
                db_path.unlink()
