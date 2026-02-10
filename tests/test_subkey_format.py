"""Test that the _redis_subkey format is now consistent with explicit separators."""

import unittest
from prometheus_distributed_client.redis import ValueClass


class SubkeyFormatTestCase(unittest.TestCase):
    """Test that _redis_subkey uses compact JSON format."""

    def test_subkey_uses_compact_json(self):
        """Verify that _redis_subkey produces compact JSON without spaces."""
        v = ValueClass(
            "counter",
            "test_metric",
            ("method", "status", "endpoint"),
            ("GET", "200", "/api"),
            help_text="Test metric",
            suffix="_created",
        )

        subkey = v._redis_subkey

        # Should be compact format without spaces
        assert " " not in subkey, "Subkey should not contain spaces"

        # Should have the correct format
        assert subkey.startswith("_created:"), "Should start with suffix"

        # Should end with compact JSON
        expected_json = '{"endpoint":"/api","method":"GET","status":"200"}'
        assert subkey == f"_created:{expected_json}"

    def test_subkey_empty_labels(self):
        """Test subkey format with no labels."""
        v = ValueClass(
            "counter",
            "test_metric",
            (),
            (),
            help_text="Test metric",
            suffix="_total",
        )

        subkey = v._redis_subkey

        # Should be compact empty dict
        assert subkey == "_total:{}"

    def test_subkey_single_label(self):
        """Test subkey format with single label."""
        v = ValueClass(
            "gauge",
            "test_gauge",
            ("status",),
            ("active",),
            help_text="Test gauge",
            suffix="",
        )

        subkey = v._redis_subkey

        # Should be compact format
        assert " " not in subkey
        assert subkey == ':{"status":"active"}'

    def test_subkey_consistency_across_calls(self):
        """Verify multiple calls to _redis_subkey produce identical output."""
        v = ValueClass(
            "counter",
            "test",
            ("a", "b", "c"),
            ("1", "2", "3"),
            help_text="Test counter",
            suffix="_created",
        )

        # Call multiple times
        subkeys = [v._redis_subkey for _ in range(100)]

        # All should be identical
        unique_subkeys = set(subkeys)
        assert len(unique_subkeys) == 1, "All subkeys should be identical"

    def test_subkey_different_instances_same_output(self):
        """Verify different ValueClass instances with same params produce same subkey."""
        params = ("counter", "test", ("x", "y"), ("1", "2"))
        kwargs = {"help_text": "Test counter", "suffix": "_total"}

        instances = [ValueClass(*params, **kwargs) for _ in range(10)]
        subkeys = [inst._redis_subkey for inst in instances]

        # All should be identical
        unique_subkeys = set(subkeys)
        assert (
            len(unique_subkeys) == 1
        ), f"Expected 1 unique subkey, got {len(unique_subkeys)}: {unique_subkeys}"


if __name__ == "__main__":
    unittest.main()
