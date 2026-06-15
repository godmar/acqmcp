from pathlib import Path

import pytest

from acqmcp.openapi_catalog import AcqOpenAPICatalog


def test_catalog_loads_operations() -> None:
    catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))

    assert "get/almaws/v1/acq/funds" in catalog.operations
    assert "put/almaws/v1/acq/vendors/{vendorCode}" in catalog.operations
    assert (
        catalog.operations["put/almaws/v1/acq/vendors/{vendorCode}"].tool_name
        == "put_acq_vendors_by_vendorCode"
    )


def test_list_operations_filters_by_tag() -> None:
    catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))

    records = catalog.list_operations(tag="Vendors", method="get")

    assert records
    assert all(record["method"] == "GET" for record in records)
    assert all("Vendors" in record["tags"] for record in records)


def test_render_path_validates_required_params() -> None:
    catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))

    rendered = catalog.render_path(
        "get/almaws/v1/acq/vendors/{vendorCode}",
        {"vendorCode": "ABC"},
    )

    assert rendered == "/almaws/v1/acq/vendors/ABC"
    with pytest.raises(ValueError, match="Missing path parameters"):
        catalog.render_path("get/almaws/v1/acq/vendors/{vendorCode}", {})
