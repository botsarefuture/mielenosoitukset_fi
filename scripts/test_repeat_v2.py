import unittest
from datetime import datetime
from scripts.repeat_v2 import calculate_next_dates

class TestCalculateNextDates(unittest.TestCase):

    def test_daily_frequency(self):
        demo_date = datetime(2023, 1, 1)
        repeat_schedule = {"frequency": "daily", "interval": 1}
        next_dates = calculate_next_dates(demo_date, repeat_schedule)
        self.assertEqual(len(next_dates), 365)
        self.assertEqual(next_dates[0], demo_date)
        self.assertEqual(next_dates[1], demo_date + timedelta(days=1))

    def test_weekly_frequency(self):
        demo_date = datetime(2023, 1, 1)
        repeat_schedule = {"frequency": "weekly", "interval": 1}
        next_dates = calculate_next_dates(demo_date, repeat_schedule)
        self.assertEqual(len(next_dates), 53)
        self.assertEqual(next_dates[0], demo_date)
        self.assertEqual(next_dates[1], demo_date + timedelta(weeks=1))

    def test_monthly_frequency(self):
        demo_date = datetime(2023, 1, 1)
        repeat_schedule = {"frequency": "monthly", "interval": 1}
        next_dates = calculate_next_dates(demo_date, repeat_schedule)
        self.assertEqual(len(next_dates), 12)
        self.assertEqual(next_dates[0], demo_date)
        self.assertEqual(next_dates[1], demo_date + relativedelta(months=1))

    def test_yearly_frequency(self):
        demo_date = datetime(2023, 1, 1)
        repeat_schedule = {"frequency": "yearly", "interval": 1}
        next_dates = calculate_next_dates(demo_date, repeat_schedule)
        self.assertEqual(len(next_dates), 2)
        self.assertEqual(next_dates[0], demo_date)
        self.assertEqual(next_dates[1], demo_date + relativedelta(years=1))

    def test_custom_interval(self):
        demo_date = datetime(2023, 1, 1)
        repeat_schedule = {"frequency": "daily", "interval": 2}
        next_dates = calculate_next_dates(demo_date, repeat_schedule)
        self.assertEqual(len(next_dates), 183)
        self.assertEqual(next_dates[0], demo_date)
        self.assertEqual(next_dates[1], demo_date + timedelta(days=2))

if __name__ == "__main__":
    unittest.main()