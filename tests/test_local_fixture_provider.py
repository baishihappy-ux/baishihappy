import unittest

from python.parser.html_parser import extract_links
from python.parser.source_profiles import PROFILES
from python.providers.local_provider import LocalFixtureProvider
from python.queue.tasks import Task, TaskStage


class LocalFixtureProviderTests(unittest.TestCase):
    def setUp(self):
        self.config = {"sources": {"source_t": {"encoded_key": "T"}}}
        self.provider = LocalFixtureProvider(self.config, enable_network=False)
        self.source_config = PROFILES["T"].from_config(self.config)

    def fetch_links(self, stage):
        task = Task(phone="2025550101", stage=stage, url=f"https://fixture.invalid/{stage.value}")
        response = self.provider.fetch(task)
        links = extract_links(response.text, response.url, self.source_config)
        return response, links

    def test_search_fixture_exposes_one_parent_detail(self):
        response, links = self.fetch_links(TaskStage.RESULTPHONE)
        self.assertTrue(response.ok)
        self.assertTrue(links["listing_page"])
        self.assertEqual(1, len(links["detail_links"]))

    def test_parent_fixture_exposes_three_associates(self):
        response, links = self.fetch_links(TaskStage.PARENT)
        self.assertTrue(response.ok)
        self.assertTrue(links["detail_page"])
        self.assertEqual(3, len(links["related_links"]))

    def test_associate_fixture_finishes_without_more_links(self):
        response, links = self.fetch_links(TaskStage.ASSOCIATE)
        self.assertTrue(response.ok)
        self.assertTrue(links["detail_page"])
        self.assertEqual([], links["related_links"])


if __name__ == "__main__":
    unittest.main()
