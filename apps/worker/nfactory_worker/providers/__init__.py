"""Worker side of the provider hub. Adapters live in `nfactory_core.providers` (shared
with the API, ADR-0006); only the offline demo provider lives here (ADR-0004)."""

from nfactory_worker.providers.fake import FAKE_MODEL_ID, FakeProvider

__all__ = ["FAKE_MODEL_ID", "FakeProvider"]
