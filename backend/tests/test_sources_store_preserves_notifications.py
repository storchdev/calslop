import json

from app.db.sources_store import SourcesStore
from app.models.dtos import SourceCreate


def test_sources_store_save_preserves_notifications_and_unknown_keys(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "sources": [],
                "notifications": {
                    "enabled": True,
                    "target": "webhook",
                    "webhook": {"url": "https://example.com/hook", "headers": {"X-Test": "1"}},
                },
                "future_key": {"keep": True},
            }
        )
    )

    store = SourcesStore(path)
    store.add_source(
        SourceCreate(
            type="ics_url",
            name="My ICS",
            config={"url": "https://calendar.example.com/a.ics"},
        )
    )

    after = json.loads(path.read_text())
    assert len(after["sources"]) == 1
    assert after["notifications"]["target"] == "webhook"
    assert after["future_key"] == {"keep": True}
