from fmt.apps import AppSpec, ImageResolver, parse_apps


def test_bare_name_defaults_to_frappe_org_and_ref():
    app = AppSpec.parse("hrms", "version-16")
    assert (app.name, app.url, app.ref) == ("hrms", "https://github.com/frappe/hrms", "version-16")


def test_name_with_ref():
    assert AppSpec.parse("hrms:v15.0.0", "version-16").ref == "v15.0.0"


def test_url_with_and_without_ref():
    with_ref = AppSpec.parse("https://github.com/org/shop.git:main", "version-16")
    assert (with_ref.name, with_ref.url, with_ref.ref) == ("shop", "https://github.com/org/shop.git", "main")
    assert AppSpec.parse("https://github.com/org/shop", "dev").ref == "dev"
    assert AppSpec.parse("git@github.com:org/shop.git", "dev").ref == "dev"


def test_serialize_round_trip():
    for text in ["hrms:version-16", "https://github.com/org/shop:main"]:
        assert AppSpec.parse(text, "x").serialize() == text


def test_official_image_for_erpnext_only():
    resolver = ImageResolver("erp", "version-16", parse_apps("erpnext", "version-16"))
    assert resolver.is_official and resolver.image == "frappe/erpnext:version-16"


def test_layered_image_when_extra_app_or_different_ref():
    extra = ImageResolver("erp", "version-16", parse_apps("erpnext,hrms", "version-16"))
    other = ImageResolver("erp", "version-16", parse_apps("erpnext:version-15", "version-16"))
    assert not extra.is_official and extra.image.startswith("fmt/erp:")
    assert extra.image != other.image


def test_apps_json_lists_url_and_branch():
    resolver = ImageResolver("erp", "v", parse_apps("hrms:main", "v"))
    assert '"branch": "main"' in resolver.apps_json
