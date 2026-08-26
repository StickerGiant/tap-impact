import unittest
from datetime import datetime, timedelta
from parameterized import parameterized

from singer import utils
from zoneinfo import ZoneInfo

from tap_impact.sync import split_date_range, to_utc_datetime

# Define DEFAULT_WINDOW_SIZE to be 45 days
DEFAULT_WINDOW_SIZE = 45


class TestSplitDateRange(unittest.TestCase):

    @parameterized.expand([
        # Test case 1: Date range with only one range (start_date and end_date within the same window)
        ("single_range",
         datetime(2024, 1, 1),
         datetime(2024, 1, 30),  # Only one 45-day window
         [(datetime(2024, 1, 1), datetime(2024, 1, 30))]),

        # Test case 2: Date range with exactly two windows
        ("two_ranges",
         datetime(2024, 1, 1),
         datetime(2024, 3, 15),  # 45 days + 45 days window
         [
             (datetime(2024, 1, 1), datetime(2024, 2, 15)),
             (datetime(2024, 2, 15), datetime(2024, 3, 15))  # Updated start date to 16th
         ]),

        # Test case 3: Date range with exactly three windows
        ("three_ranges",
         datetime(2024, 1, 1),
         datetime(2024, 4, 10),  # 45 days + 45 days + 45 days
         [
             (datetime(2024, 1, 1), datetime(2024, 2, 15)),
             (datetime(2024, 2, 15), datetime(2024, 3, 31)),
             (datetime(2024, 3, 31), datetime(2024, 4, 10))  # Updated start date to 3rd
         ]),

        # Test case 4: Date range where end_date is before start_date (empty range)
        ("no_range",
         datetime(2024, 3, 15),
         datetime(2024, 1, 1),  # end_date is before start_date
         []),

        # Test case 5: Date range with start_date and end_date being the same (single range)
        ("same_date",
         datetime(2024, 1, 1),
         datetime(2024, 1, 1),  # start_date == end_date
         []),  # Expecting an empty range

        # Test case 6: Date range spanning multiple months (more than two windows)
        ("multiple_ranges",
         datetime(2024, 1, 1),
         datetime(2024, 6, 10),  # 45 days + 45 days + 45 days + 45 days
         [
             (datetime(2024, 1, 1), datetime(2024, 2, 15)),
             (datetime(2024, 2, 15), datetime(2024, 3, 31)),
             (datetime(2024, 3, 31), datetime(2024, 5, 15)),
             (datetime(2024, 5, 15), datetime(2024, 6, 10))  # Updated start date to 16th
         ]),
    ])
    def test_split_date_range(self, name, start_date, end_date, expected_ranges):
        """Test splitting a date range into smaller ranges."""
        actual_ranges = split_date_range(start_date, end_date)

        # Compare the length of actual_ranges and expected_ranges
        self.assertEqual(len(actual_ranges), len(expected_ranges), f"Length mismatch for {name}. "
                                                                   f"Expected {len(expected_ranges)} but got {len(actual_ranges)}.")

        # Compare the actual result with the expected result
        self.assertEqual(actual_ranges, expected_ranges)


class TestToUtcDatetime(unittest.TestCase):
    """
    Regression cover for the naive/aware mismatch that broke actions syncs:
    a configured start_date such as '2025-01-01' parses naive, and comparing it
    against the aware utils.now() in split_date_range raised
    "can't compare offset-naive and offset-aware datetimes".
    """

    def test_bare_date_is_assumed_utc(self):
        result = to_utc_datetime('2025-01-01')
        self.assertEqual(result, datetime(2025, 1, 1, tzinfo=ZoneInfo('UTC')))
        self.assertIsNotNone(result.tzinfo)

    def test_zulu_timestamp_is_utc(self):
        result = to_utc_datetime('2026-08-26T16:14:44Z')
        self.assertEqual(result, datetime(2026, 8, 26, 16, 14, 44, tzinfo=ZoneInfo('UTC')))

    def test_explicit_offset_keeps_the_instant(self):
        # A stated offset must be converted, not overwritten: 18:00+02:00 is 16:00 UTC.
        result = to_utc_datetime('2026-08-26T18:00:00+02:00')
        self.assertEqual(result, datetime(2026, 8, 26, 16, 0, 0, tzinfo=ZoneInfo('UTC')))

    def test_result_is_comparable_with_singer_now(self):
        # The actual failure mode: this comparison used to raise TypeError.
        self.assertLess(to_utc_datetime('2025-01-01'), utils.now())

    def test_split_date_range_accepts_a_bare_config_start_date(self):
        ranges = split_date_range(to_utc_datetime('2025-01-01'), utils.now())
        self.assertGreater(len(ranges), 1)
        self.assertTrue(all(s < e for s, e in ranges))
