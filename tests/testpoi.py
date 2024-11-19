from poi_scraper.poi import Link


class TestLinkCreation:
    def test_create_link(self) -> None:
        link = Link.create(parent=None, url="https://example.com", estimated_score=5)

        assert link.url == "https://example.com"
        assert link.estimated_score == 5
        assert link.parents == set()
        assert not link.visited
        assert link.children == set()
        assert link.children_visited == 0
        assert link.children_poi_found == 0


class TestPoiScore:
    def test_score(self) -> None:
        home = Link.create(parent=None, url="https://example.com", estimated_score=5)
        assert home.score == 5

        home.record_visit(
            poi_found=False,
            urls_found={
                "https://example.com/places": 4,
                "https://example.com/about": 3,
            },
        )
        places = home.site.urls["https://example.com/places"]
        about = home.site.urls["https://example.com/about"]

        places.record_visit(
            poi_found=True,
            urls_found={
                "https://example.com/places/something_else": 4,
            },
        )

        # should be almost equal
        # assert *.score == 5 + (1-math.exp(-0.2))
        assert home.score == 5.0, home.score
        assert round(places.score, 3) == 4.091
        assert round(about.score, 3) == 3.091

        about.record_visit(
            poi_found=True,
            urls_found={},
        )
        assert home.score == 5.0, home.score
        assert round(places.score, 3) == 4.165
        assert round(about.score, 3) == 3.165

        scores = home.site.get_url_scores(decimals=3)
        expected = {
            "https://example.com": 5.0,
            "https://example.com/about": 3.165,
            "https://example.com/places": 4.165,
            "https://example.com/places/something_else": 4,
        }
        assert scores == expected
