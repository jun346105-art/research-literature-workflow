import json

from litflow.zotero.client import ZoteroReadClient
from litflow.zotero.collection_reader import read_collection, write_collection_snapshot
from litflow.zotero.diagnostics import write_citekey_diagnostics


class FakeZoteroClient:
    def __init__(self):
        self.collections = [{"key": "C1", "data": {"name": "Research"}}]
        self.items = {
            "C1": [
                {
                    "key": "I1",
                    "data": {
                        "key": "I1",
                        "itemType": "journalArticle",
                        "title": "Paper One",
                        "creators": [
                            {"firstName": "Alice", "lastName": "Wang"},
                            {"name": "Bob Smith"},
                        ],
                        "date": "2024-05-01",
                        "publicationTitle": "Journal of Tests",
                        "DOI": "10.1/demo",
                        "url": "https://example.com",
                        "abstractNote": "Abstract text.",
                        "extra": "Citation Key: wang2024paper\nOther: value",
                        "tags": [{"tag": "rgbd"}, {"tag": "defect"}],
                    },
                },
                {
                    "key": "I2",
                    "data": {
                        "key": "I2",
                        "itemType": "conferencePaper",
                        "title": "Paper Two",
                        "creators": [{"firstName": "Carol", "lastName": "Li"}],
                        "date": "no date",
                        "conferenceName": "TestConf",
                        "tags": [],
                    },
                },
                {
                    "key": "N1",
                    "data": {
                        "key": "N1",
                        "itemType": "note",
                        "title": "",
                    },
                },
            ]
        }
        self.children = {
            "I1": [
                {
                    "key": "A1",
                    "data": {
                        "key": "A1",
                        "itemType": "attachment",
                        "title": "paper.pdf",
                        "contentType": "application/pdf",
                    },
                },
                {
                    "key": "A2",
                    "data": {
                        "key": "A2",
                        "itemType": "attachment",
                        "title": "supplement.pdf",
                        "contentType": "application/pdf",
                    },
                },
                {
                    "key": "A3",
                    "data": {
                        "key": "A3",
                        "itemType": "attachment",
                        "title": "snapshot.html",
                        "contentType": "text/html",
                    },
                },
            ],
            "I2": [],
        }
        self.paths = {"A1": "C:/papers/paper.pdf", "A2": "C:/papers/supplement.pdf"}
        self.all_items = [item for items in self.items.values() for item in items]

    def get_collections(self):
        return self.collections

    def get_collection_items(self, collection_key):
        return self.items[collection_key]

    def get_items(self):
        return self.all_items

    def get_item_children(self, item_key):
        return self.children[item_key]

    def get_attachment_file_path(self, attachment_key):
        return self.paths.get(attachment_key)


def test_read_collection_maps_zotero_metadata():
    papers = read_collection("Research", FakeZoteroClient())

    paper = papers[0]
    assert paper.zotero_key == "I1"
    assert paper.citation_key == "wang2024paper"
    assert paper.citation_key_source == "extra_field"
    assert paper.title == "Paper One"
    assert paper.authors == ["Alice Wang", "Bob Smith"]
    assert paper.year == 2024
    assert paper.venue == "Journal of Tests"
    assert paper.doi == "10.1/demo"
    assert paper.url == "https://example.com"
    assert paper.abstract == "Abstract text."
    assert paper.item_type == "journalArticle"
    assert paper.collection == "Research"
    assert paper.tags == ["rgbd", "defect"]


def test_read_collection_handles_missing_doi_pdf_citation_key_and_abstract():
    papers = read_collection("Research", FakeZoteroClient())

    paper = papers[1]
    assert paper.doi is None
    assert paper.pdf_attachment_path is None
    assert paper.pdf_exists is False
    assert paper.citation_key is None
    assert paper.citation_key_source == "missing"
    assert paper.abstract is None
    assert paper.year is None


def test_read_collection_handles_multiple_attachments():
    papers = read_collection("Research", FakeZoteroClient())

    paper = papers[0]
    assert paper.attachment_count == 3
    assert paper.pdf_attachment_path == "C:/papers/paper.pdf"
    assert paper.pdf_exists is False


def test_read_collection_missing_collection_fails():
    try:
        read_collection("Missing", FakeZoteroClient())
    except ValueError as exc:
        assert "Zotero collection not found: Missing" in str(exc)
    else:
        raise AssertionError("expected missing collection to fail")


def test_write_collection_snapshot_creates_json(tmp_path):
    output = tmp_path / "zotero_collection.json"

    papers = write_collection_snapshot("Research", output, FakeZoteroClient())

    data = json.loads(output.read_text(encoding="utf-8"))
    assert len(papers) == 2
    assert data["metadata"]["source"] == "zotero"
    assert data["metadata"]["collection"] == "Research"
    assert data["metadata"]["read_only"] is True
    assert data["metadata"]["citation_key_count"] == 1
    assert data["metadata"]["citation_key_missing_count"] == 1
    assert data["metadata"]["citation_key_sources"] == {"extra_field": 1, "missing": 1}
    assert data["papers"][0]["zotero_key"] == "I1"


def test_read_collection_extracts_data_citation_key():
    client = FakeZoteroClient()
    client.items["C1"][0]["data"]["citationKey"] = "better2024key"
    client.items["C1"][0]["data"]["extra"] = ""

    paper = read_collection("Research", client)[0]

    assert paper.citation_key == "better2024key"
    assert paper.citation_key_source == "better_bibtex"


def test_read_collection_extracts_data_citekey():
    client = FakeZoteroClient()
    client.items["C1"][0]["data"]["citekey"] = "field2024key"
    client.items["C1"][0]["data"]["extra"] = ""

    paper = read_collection("Research", client)[0]

    assert paper.citation_key == "field2024key"
    assert paper.citation_key_source == "zotero_field"


def test_read_collection_skips_notes():
    papers = read_collection("Research", FakeZoteroClient())

    assert [paper.zotero_key for paper in papers] == ["I1", "I2"]


def test_read_collection_falls_back_to_item_collections_when_collection_endpoint_is_empty():
    client = FakeZoteroClient()
    for item in client.items["C1"]:
        item["data"]["collections"] = ["C1"]
    client.items["C1"] = []

    papers = read_collection("Research", client)

    assert [paper.zotero_key for paper in papers] == ["I1", "I2"]


def test_zotero_client_normalizes_windows_file_url(monkeypatch):
    client = ZoteroReadClient()
    monkeypatch.setattr(client, "_get_text", lambda path: "file:///C:/Users/Example/Zotero/storage/A/paper.pdf")

    assert client.get_attachment_file_path("A1") == "C:\\Users\\Example\\Zotero\\storage\\A\\paper.pdf"


def test_write_citekey_diagnostics_creates_json(tmp_path):
    output = tmp_path / "zotero_citekey_diagnostics.json"

    report = write_citekey_diagnostics("Research", output, FakeZoteroClient())
    saved = json.loads(output.read_text(encoding="utf-8"))

    assert report["metadata"]["total_items"] == 2
    assert saved["metadata"]["citation_key_count"] == 1
    assert saved["metadata"]["citation_key_missing_count"] == 1
    assert saved["items"][0]["citation_key"] == "wang2024paper"
    assert saved["items"][0]["citation_key_source"] == "extra_field"
    assert "data.extra" in saved["items"][0]["raw_candidate_fields"]
