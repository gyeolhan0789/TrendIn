from trendin.dev import example


def test_active_sources_is_a_list_for_dynamic_mapping():
    sources = example.load_active_sources()
    assert isinstance(sources, list)
    assert sources == ["hacker_news", "example_blog"]


def test_collect_source_returns_count():
    assert example.collect_source("hacker_news") == 11


def test_sum_counts_skips_missing_xcom_from_failed_instances():
    assert example.sum_counts([3, None, 4]) == 7
