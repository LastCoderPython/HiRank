from app.services.profile_enricher import ProfileEnricher

enricher = ProfileEnricher()


class TestExtract:
    def test_extract_exam_jee_main(self):
        result = enricher.extract("I scored well in JEE Mains")
        assert result.get("exam") == "JEE_MAIN"

    def test_extract_exam_jee_advanced(self):
        result = enricher.extract("Preparing for JEE Advanced 2025")
        assert result.get("exam") == "JEE_ADV"

    def test_extract_exam_neet(self):
        result = enricher.extract("NEET 2025 results")
        assert result.get("exam") == "NEET"

    def test_extract_exam_cee(self):
        result = enricher.extract("CEE Assam exam")
        assert result.get("exam") == "CEE"

    def test_extract_rank(self):
        result = enricher.extract("4521 rank")
        assert result.get("rank") == 4521

    def test_extract_rank_air_format(self):
        result = enricher.extract("12345 air")
        assert result.get("rank") == 12345

    def test_extract_percentile(self):
        result = enricher.extract("94.5 percentile")
        assert result.get("percentile") == 94.5

    def test_extract_percentile_pct_format(self):
        result = enricher.extract("99.2%ile in JEE Mains")
        assert result.get("percentile") == 99.2

    def test_extract_category_obc(self):
        result = enricher.extract("OBC category")
        assert result.get("category") == "OBC"

    def test_extract_category_sc(self):
        result = enricher.extract("SC category student")
        assert result.get("category") == "SC"

    def test_extract_category_st(self):
        result = enricher.extract("ST candidate")
        assert result.get("category") == "ST"

    def test_extract_category_ews(self):
        result = enricher.extract("EWS category")
        assert result.get("category") == "EWS"

    def test_extract_category_general(self):
        result = enricher.extract("General category")
        assert result.get("category") == "General"

    def test_extract_category_open(self):
        result = enricher.extract("Open category")
        assert result.get("category") == "General"

    def test_extract_combined(self):
        result = enricher.extract("4521 rank, 94.5 percentile, JEE Main, OBC-NCL")
        assert result.get("exam") == "JEE_MAIN"
        assert result.get("rank") == 4521
        assert result.get("percentile") == 94.5
        assert result.get("category") == "OBC"

    def test_extract_empty_message(self):
        result = enricher.extract("")
        assert result == {}

    def test_extract_no_match(self):
        result = enricher.extract("What are the top engineering colleges?")
        assert result == {}

    def test_extract_sc_not_science(self):
        result = enricher.extract("Computer Science is my subject")
        assert result.get("category") != "SC"
