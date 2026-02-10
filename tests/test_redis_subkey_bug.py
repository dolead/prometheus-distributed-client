"""Test that demonstrates the Redis subkey duplicate bug.

This test will FAIL if json.dumps() uses default separators (with spaces)
and PASS only when explicit compact separators are used.
"""

import json
import unittest

from prometheus_distributed_client.redis import ValueClass


class RedisSubkeyBugTestCase(unittest.TestCase):
    """Test that reproduces the duplicate _created key bug."""

    def test_subkey_must_not_contain_spaces(self):
        """CRITICAL: Subkeys must not contain spaces to prevent duplicate keys.

        Without explicit separators, json.dumps() produces:
            '{"method": "GET"}' (with spaces)

        With explicit separators=(',', ':'), it produces:
            '{"method":"GET"}' (no spaces)

        If both formats exist in Redis, you get duplicate _created keys:
            _created:{"method": "GET"}
            _created:{"method":"GET"}

        This test will FAIL if spaces are present.
        """
        v = ValueClass(
            "counter",
            "test_metric",
            ("method", "status"),
            ("GET", "200"),
            help_text="Test metric",
            suffix="_created"
        )

        subkey = v._redis_subkey

        # This will FAIL if default separators are used (which include spaces)
        assert " " not in subkey, \
            f"Subkey contains spaces: {repr(subkey)}. " \
            f"This will cause duplicate keys in Redis! " \
            f"Expected compact format without spaces."

    def test_subkey_matches_explicit_compact_format(self):
        """Verify subkey uses explicit compact JSON format.

        This test constructs the expected format using explicit separators
        and compares it to what ValueClass produces.
        """
        labels = {"method": "GET", "status": "200"}

        # What we expect: compact JSON with explicit separators
        expected_json = json.dumps(labels, sort_keys=True, separators=(',', ':'))
        expected_subkey = f"_created:{expected_json}"

        # What the code produces
        v = ValueClass(
            "counter",
            "test_metric",
            ("method", "status"),
            ("GET", "200"),
            help_text="Test metric",
            suffix="_created"
        )
        actual_subkey = v._redis_subkey

        # These must match exactly
        assert actual_subkey == expected_subkey, \
            f"Subkey format mismatch!\n" \
            f"Expected (compact): {repr(expected_subkey)}\n" \
            f"Actual:            {repr(actual_subkey)}\n" \
            f"This indicates separators are not explicitly set."

    def test_default_json_dumps_has_spaces(self):
        """Document that default json.dumps() includes spaces.

        This is a sanity check to verify our understanding of the bug.
        """
        labels = {"method": "GET", "status": "200"}

        # Default json.dumps includes spaces
        default_json = json.dumps(labels, sort_keys=True)
        assert " " in default_json, \
            f"Expected default json.dumps to include spaces, got: {repr(default_json)}"

        # Compact format does not
        compact_json = json.dumps(labels, sort_keys=True, separators=(',', ':'))
        assert " " not in compact_json, \
            f"Expected compact json.dumps to have no spaces, got: {repr(compact_json)}"

        # They should be different
        assert default_json != compact_json, \
            "Default and compact JSON should differ"

    def test_empty_labels_must_be_compact(self):
        """Even empty labels dict must use compact format."""
        v = ValueClass(
            "counter",
            "test_metric",
            (),
            (),
            help_text="Test metric",
            suffix="_total"
        )

        subkey = v._redis_subkey

        # Must be exactly "_total:{}" with no spaces
        assert subkey == "_total:{}", \
            f"Expected '_total:{{}}', got {repr(subkey)}"

        # Verify no spaces
        assert " " not in subkey


if __name__ == "__main__":
    unittest.main()
