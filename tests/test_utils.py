import sys
import os
from datetime import datetime
from unittest.mock import patch

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.routes import time_to_minutes, format_time_range, get_current_day_index


def test_time_to_minutes():
    assert time_to_minutes("9:00") == 540
    assert time_to_minutes("10:50") == 650
    assert time_to_minutes("12:40") == 760
    assert time_to_minutes("14:55") == 895
    assert time_to_minutes("18:30") == 1110


def test_format_time_range():
    assert format_time_range("9:00 Четная") == "9:00 – 10:30"
    assert format_time_range("10:50 Нечетная") == "10:50 – 12:20"
    assert format_time_range("12:40") == "12:40 – 14:10"
    assert format_time_range("14:55") == "14:55 – 16:25"
    assert format_time_range("18:30") == "18:30 – 20:00"

    assert format_time_range("без времени") == "без времени"



@patch('handlers.routes.datetime')
def test_get_current_day_index_monday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 15)  # понедельник
    assert get_current_day_index() == 0

@patch('handlers.routes.datetime')
def test_get_current_day_index_tuesday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 16)  # вторник
    assert get_current_day_index() == 1

@patch('handlers.routes.datetime')
def test_get_current_day_index_sunday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 14)  # воскресенье
    assert get_current_day_index() == 0

@patch('handlers.routes.datetime')
def test_get_current_day_index_saturday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 13)  # суббота
    assert get_current_day_index() == 5