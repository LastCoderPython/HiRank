"""Tests for domain registry constants and DomainRegistry class."""

from __future__ import annotations

from urllib.parse import urlparse

from app.services.domain_registry import (
    COLLEGE_DOMAINS,
    START_URLS,
    ALL_OFFICIAL_DOMAINS,
    DomainRegistry,
)

domain_registry = DomainRegistry()


class TestCollegeDomains:
    def test_known_colleges_exist(self):
        expected = {"AEC", "JEC", "NITS", "TU", "GU", "DU", "JIST"}
        for code in expected:
            assert code in COLLEGE_DOMAINS, f"Missing {code}"

    def test_each_college_has_domains(self):
        for code, domains in COLLEGE_DOMAINS.items():
            assert len(domains) > 0, f"{code} has no domains"

    def test_start_urls_all_valid_domains(self):
        for url in START_URLS:
            parsed = urlparse(url)
            assert parsed.hostname in ALL_OFFICIAL_DOMAINS, (
                f"{url} hostname not in ALL_OFFICIAL_DOMAINS"
            )

    def test_all_official_domains_is_populated(self):
        assert len(ALL_OFFICIAL_DOMAINS) > 0


class TestDomainContent:
    def test_no_empty_urls(self):
        for url in START_URLS:
            assert url.startswith("https://"), f"Non-HTTPS: {url}"

    def test_no_duplicates_in_start_urls(self):
        assert len(START_URLS) == len(set(START_URLS)), "Duplicate START_URLS"

    def test_all_urls_use_https(self):
        for url in START_URLS:
            assert url.startswith("https://"), f"Non-HTTPS: {url}"


class TestDomainRegistryGetDomains:
    def test_get_known_college(self):
        assert domain_registry.get_domains("AEC") == ["aec.ac.in", "www.aec.ac.in"]

    def test_get_unknown_college(self):
        assert domain_registry.get_domains("NONEXISTENT") == []

    def test_get_case_insensitive(self):
        assert domain_registry.get_domains("aec") == ["aec.ac.in", "www.aec.ac.in"]


class TestDomainRegistryClassifyUrl:
    def test_classify_official(self):
        assert domain_registry.classify_url("https://www.aec.ac.in/") == "official"

    def test_classify_official_without_www(self):
        assert domain_registry.classify_url("https://aec.ac.in/") == "official"

    def test_classify_educational(self):
        assert domain_registry.classify_url("https://somecollege.ac.in/") == "educational"

    def test_classify_unofficial(self):
        assert domain_registry.classify_url("https://reddit.com/r/college") == "unofficial"

    def test_classify_invalid_url(self):
        assert domain_registry.classify_url("") == "unofficial"


class TestDomainRegistryIsTrusted:
    def test_official_is_trusted(self):
        assert domain_registry.is_trusted("https://www.aec.ac.in/") is True

    def test_educational_is_trusted(self):
        assert domain_registry.is_trusted("https://somecollege.ac.in/") is True

    def test_unofficial_not_trusted(self):
        assert domain_registry.is_trusted("https://shiksha.com/colleges") is False


class TestDomainRegistryBuildSiteFilter:
    def test_build_site_filter_for_college(self):
        result = domain_registry.build_site_filter("AEC")
        assert isinstance(result, list)
        assert "aec.ac.in" in result

    def test_build_site_filter_no_college(self):
        result = domain_registry.build_site_filter()
        assert isinstance(result, list)
        assert len(result) > 0
