from answer_contract_support import *  # noqa: F401,F403

def test_site_bundle_requested_colors_appear_in_css() -> None:
    from core.brain import site_bundle as sb

    pages = ["index.html", "assets/site.css"]
    files = sb.build_bundle_files(
        business_name="Fuze Boxx",
        slug="fuze-boxx",
        pages=pages,
        style_hints={"colors": ["#1a1a2e", "#e94560", "#f0f0f0"], "styles": []},
        question="website",
    )
    css_file = next(f for f in files if f["path"].endswith(".css"))
    assert "#1a1a2e" in css_file["content"]
    assert "#e94560" in css_file["content"]

def test_site_bundle_unsafe_paths_rejected() -> None:
    from core.brain import site_bundle as sb

    assert not sb.is_safe_bundle_path("../../../etc/passwd")
    assert not sb.is_safe_bundle_path("/absolute/path.html")
    assert not sb.is_safe_bundle_path("C:\\windows\\path.html")
    assert not sb.is_safe_bundle_path("page;rm -rf /.html")
    assert sb.is_safe_bundle_path("index.html")
    assert sb.is_safe_bundle_path("assets/site.css")

def test_site_bundle_validate_requires_entry_file() -> None:
    from core.brain import site_bundle as sb

    files = [
        {
            "path": "about.html",
            "language": "html",
            "content": "<html><body>about</body></html>",
        },
        {
            "path": "menu.html",
            "language": "html",
            "content": "<html><body>menu</body></html>",
        },
    ]
    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="",
        style_hints={},
    )
    assert not passed
    assert any("entry file" in f for f in failures)

def test_site_bundle_validate_requires_two_html_pages() -> None:
    from core.brain import site_bundle as sb

    files = [
        {
            "path": "index.html",
            "language": "html",
            "content": "<html><body>home</body></html>",
        }
    ]
    passed, failures = sb.validate_bundle(
        bundle_files=files,
        entry="index.html",
        business_name="",
        style_hints={},
    )
    assert not passed
    assert any("2" in f or "html pages" in f.lower() for f in failures)

def test_site_bundle_generation_returns_bundle_payload_without_writing_files(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a 5 page website for Tony's Tavern biker bar using black orange and yellow",
            session_messages=[],
            session_metadata={},
        )
    )
    assert response is not None
    site_bundle_data = response.get("site_bundle")
    assert isinstance(site_bundle_data, dict), (
        f"expected site_bundle, got: {list(response.keys())}"
    )
    assert site_bundle_data.get("artifact_type") == "site_bundle"
    assert "tony" in site_bundle_data.get("title", "").lower()
    bundle_files = (site_bundle_data.get("site_bundle") or {}).get("files", [])
    assert len(bundle_files) >= 5
    paths = [f["path"] for f in bundle_files]
    assert "index.html" in paths
    assert "menu.html" in paths or "services.html" in paths
    assert "contact.html" in paths
    assert any(p.endswith(".css") for p in paths)
    assert not response.get("code_artifact")
    assert not (tmp_path / "generated-sites").exists()

def test_direct_website_build_writes_bundle_to_sandbox(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path / "sandbox"))
    contract = AnswerContract()

    response = asyncio.run(
        contract.build_code_artifact_response(
            "build me a website for Harry's Hot Dog Cart",
            session_messages=[],
            session_metadata={},
        )
    )

    assert response is not None
    provenance = response.get("provenance", {})
    assert provenance.get("artifact_generation") == "sandbox_build"
    written = provenance.get("files_written")
    assert isinstance(written, list)
    assert "harry-s-hot-dog-cart/index.html" in written
    assert (tmp_path / "sandbox" / "harry-s-hot-dog-cart" / "index.html").exists()

def test_export_approved_website_writes_latest_bundle_to_sandbox(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(tmp_path / "sandbox"))
    contract = AnswerContract()
    bundle_artifact = {
        "artifact_type": "site_bundle",
        "artifact_id": "harrys-hot-dog-cart-bundle",
        "revision_id": "harrys-hot-dog-cart-bundle:r1",
        "revision_number": 1,
        "title": "Harry's Hot Dog Cart",
        "slug": "harrys-hot-dog-cart",
        "entry": "index.html",
        "source_prompt": "generate a website for Harry's Hot Dog Cart",
        "site_bundle": {
            "files": [
                {
                    "path": "index.html",
                    "language": "html",
                    "content": "<!doctype html><html><body>Harry's Hot Dog Cart</body></html>",
                },
                {
                    "path": "assets/site.css",
                    "language": "css",
                    "content": "body { color: red; }",
                },
            ]
        },
    }

    response = asyncio.run(
        contract.build_code_artifact_response(
            "export the approved website",
            session_messages=[
                {
                    "role": "assistant",
                    "content": "Here is the preview.",
                    "metadata": {"site_bundle": bundle_artifact},
                }
            ],
            session_metadata={},
        )
    )

    assert response is not None
    provenance = response.get("provenance", {})
    assert provenance.get("artifact_generation") == "sandbox_build"
    assert (tmp_path / "sandbox" / "harrys-hot-dog-cart" / "index.html").exists()

def test_site_bundle_revision_adds_requested_page_and_less_generic_detail(
    monkeypatch, tmp_path
) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    initial = asyncio.run(
        contract.build_code_artifact_response(
            "generate a website for Syfernetics, cybersecurity AI professional style",
            session_messages=[],
            session_metadata={},
        )
    )
    assert initial is not None
    initial_bundle = initial["site_bundle"]

    revised = asyncio.run(
        contract.build_code_artifact_response(
            "make it look less generic and add a menu page",
            session_messages=[
                {
                    "role": "assistant",
                    "content": initial["visible_text"],
                    "metadata": {"site_bundle": initial_bundle},
                }
            ],
            session_metadata={},
        )
    )

    assert revised is not None
    files = revised["site_bundle"]["site_bundle"]["files"]
    by_path = {item["path"]: item["content"] for item in files}
    assert "menu.html" in by_path
    assert "Not a blank template" in by_path["index.html"]
    assert "Security assessment" in by_path["services.html"]

def test_site_bundle_preview_revision_export_preserves_active_design_parity(
    monkeypatch, tmp_path
) -> None:
    sandbox_root = tmp_path / "sandbox"
    monkeypatch.setenv("XV7_SANDBOX_ROOT", str(sandbox_root))
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path / "patches"))
    contract = AnswerContract()

    initial = asyncio.run(
        contract.build_code_artifact_response(
            "generate a website for Harry's Hot Dog Cart, bright red and yellow, fun street-food style",
            session_messages=[],
            session_metadata={},
        )
    )
    assert initial is not None
    assert initial["provenance"]["artifact_generation"] == "site_bundle"
    assert not sandbox_root.exists()
    initial_bundle = initial["site_bundle"]
    initial_spec = initial_bundle["design_spec"]
    assert initial_spec["business_name"] == "Harry's Hot Dog Cart"
    assert initial_spec["business_type"] == "food"
    assert initial_spec["tone"] == "fun street-food"
    assert initial_spec["cta_strategy"]["primary"] == "Order catering"
    assert initial_spec["visual_direction"]
    assert initial_spec["palette"]["requested_colors"] == ["red", "yellow"]

    revised = asyncio.run(
        contract.build_code_artifact_response(
            "make it look less generic and add a menu page",
            session_messages=[
                {
                    "role": "assistant",
                    "content": initial["visible_text"],
                    "metadata": {"site_bundle": initial_bundle},
                }
            ],
            session_metadata={},
        )
    )
    assert revised is not None
    assert revised["provenance"]["artifact_generation"] == "site_bundle_refinement"
    assert not sandbox_root.exists()
    revised_bundle = revised["site_bundle"]
    revised_spec = revised_bundle["design_spec"]
    assert revised_spec["business_name"] == initial_spec["business_name"]
    assert revised_spec["business_type"] == initial_spec["business_type"]
    assert revised_spec["tone"] == initial_spec["tone"]
    assert revised_spec["cta_strategy"] == initial_spec["cta_strategy"]
    assert revised_spec["visual_direction"] == initial_spec["visual_direction"]
    assert revised_spec["palette"]["requested_colors"] == ["red", "yellow"]

    revised_files = revised_bundle["site_bundle"]["files"]
    revised_by_path = {item["path"]: item["content"] for item in revised_files}
    assert "menu.html" in revised_by_path
    assert "Not a blank template" in revised_by_path["index.html"]
    assert "Classic Street Dog" in revised_by_path["menu.html"]

    exported = asyncio.run(
        contract.build_code_artifact_response(
            "build the approved website to sandbox",
            session_messages=[
                {
                    "role": "assistant",
                    "content": initial["visible_text"],
                    "metadata": {"site_bundle": initial_bundle},
                },
                {
                    "role": "assistant",
                    "content": revised["visible_text"],
                    "metadata": {"site_bundle": revised_bundle},
                },
            ],
            session_metadata={},
        )
    )
    assert exported is not None
    assert exported["provenance"]["artifact_generation"] == "sandbox_build"
    exported_bundle = exported["site_bundle"]
    assert exported_bundle["design_spec"] == revised_spec
    assert exported_bundle["site_bundle"]["files"] == revised_files

    written = exported["provenance"]["files_written"]
    assert "harry-s-hot-dog-cart/index.html" in written
    assert "harry-s-hot-dog-cart/menu.html" in written
    exported_index = sandbox_root / "harry-s-hot-dog-cart" / "index.html"
    exported_menu = sandbox_root / "harry-s-hot-dog-cart" / "menu.html"
    assert exported_index.read_text(encoding="utf-8") == revised_by_path["index.html"]
    assert exported_menu.read_text(encoding="utf-8") == revised_by_path["menu.html"]
    assert "Local Business Website" not in exported_index.read_text(encoding="utf-8")
    assert all(
        (sandbox_root / rel).resolve().is_relative_to(sandbox_root.resolve())
        for rel in written
    )

def test_site_bundle_patch_proposal_covers_all_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    bundle_artifact = {
        "artifact_type": "site_bundle",
        "artifact_id": "tonys-tavern-bundle",
        "revision_id": "tonys-tavern-bundle:r1",
        "revision_number": 1,
        "title": "Tony's Tavern",
        "slug": "tonys-tavern",
        "entry": "index.html",
        "source_prompt": "create a website",
        "site_bundle": {
            "files": [
                {
                    "path": "index.html",
                    "language": "html",
                    "content": "<!doctype html><html><body>Tony's Tavern</body></html>",
                },
                {
                    "path": "menu.html",
                    "language": "html",
                    "content": "<!doctype html><html><body>Tony's Tavern Menu</body></html>",
                },
                {
                    "path": "assets/site.css",
                    "language": "css",
                    "content": "body { background: #000; }",
                },
            ]
        },
    }
    response = asyncio.run(
        contract.build_code_artifact_response(
            "generate a patch for this site",
            session_messages=[
                {
                    "role": "user",
                    "content": "create a website for Tony's Tavern",
                    "metadata": {},
                },
                {
                    "role": "assistant",
                    "content": "Here is the bundle.",
                    "metadata": {"site_bundle": bundle_artifact},
                },
            ],
            session_metadata={},
        )
    )
    assert response is not None
    proposals = response.get("site_bundle_patch_proposals")
    assert isinstance(proposals, list), "expected site_bundle_patch_proposals"
    assert len(proposals) == 3
    target_paths = [p["target_path"] for p in proposals]
    assert "generated-sites/tonys-tavern/index.html" in target_paths
    assert "generated-sites/tonys-tavern/menu.html" in target_paths
    assert "generated-sites/tonys-tavern/assets/site.css" in target_paths
    assert not (tmp_path / "generated-sites" / "tonys-tavern" / "index.html").exists()

def test_site_bundle_apply_writes_all_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    contract = AnswerContract()
    bundle_artifact = {
        "artifact_type": "site_bundle",
        "slug": "tonys-tavern",
        "entry": "index.html",
    }
    proposals = [
        {
            "type": "artifact_patch_proposal",
            "proposal_id": "patch-aaa",
            "target_path": "generated-sites/tonys-tavern/index.html",
            "operation": "create",
            "language": "html",
            "applied": False,
            "requires_confirmation": True,
            "content": "<!doctype html><html><body>Tony's Tavern</body></html>",
            "diff": "",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
        {
            "type": "artifact_patch_proposal",
            "proposal_id": "patch-bbb",
            "target_path": "generated-sites/tonys-tavern/assets/site.css",
            "operation": "create",
            "language": "css",
            "applied": False,
            "requires_confirmation": True,
            "content": "body { background: #000; }",
            "diff": "",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
    ]
    response = asyncio.run(
        contract.build_code_artifact_response(
            "apply the patch",
            session_messages=[
                {"role": "user", "content": "generate a patch", "metadata": {}},
                {
                    "role": "assistant",
                    "content": "Patch proposals ready.",
                    "metadata": {
                        "site_bundle": bundle_artifact,
                        "site_bundle_patch_proposals": proposals,
                    },
                },
            ],
            session_metadata={},
        )
    )
    assert response is not None
    provenance = response.get("provenance", {})
    assert provenance.get("artifact_patch") == "bundle_applied"
    assert (tmp_path / "generated-sites" / "tonys-tavern" / "index.html").exists()
    assert (
        tmp_path / "generated-sites" / "tonys-tavern" / "assets" / "site.css"
    ).exists()

def test_site_bundle_unsafe_apply_is_blocked(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("XV7_ARTIFACT_PATCH_ROOT", str(tmp_path))
    from core.brain import site_bundle as sb

    bad_proposals = [
        {
            "target_path": "../../../evil.html",
            "operation": "create",
            "language": "html",
            "applied": False,
            "content": "<html>evil</html>",
            "validation": {"status": "passed", "checks": [], "failures": []},
        },
    ]
    written, errors = sb.apply_proposals(
        proposals=bad_proposals,
        root=tmp_path,
        resolve_fn=AnswerContract._resolve_safe_patch_target,
    )
    assert len(written) == 0, "unsafe paths must not be written"
    assert len(errors) > 0
