import sys
import os
from datetime import datetime
from unittest.mock import patch, AsyncMock
import pytest
import asyncio

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from handlers.routes import (
    time_to_minutes,
    format_time_range,
    get_current_day_index,
    FAQ_ITEMS,
    get_faq_keyboard,
    fetch_news
)


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
    mock_datetime.today.return_value = datetime(2026, 6, 15)  # пн
    assert get_current_day_index() == 0


@patch('handlers.routes.datetime')
def test_get_current_day_index_tuesday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 16)  # вт
    assert get_current_day_index() == 1


@patch('handlers.routes.datetime')
def test_get_current_day_index_sunday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 14)  # вс
    assert get_current_day_index() == 0


@patch('handlers.routes.datetime')
def test_get_current_day_index_saturday(mock_datetime):
    mock_datetime.today.return_value = datetime(2026, 6, 13)  # сб
    assert get_current_day_index() == 5


# ---------- Тесты для FAQ ----------
def test_faq_items_structure():
    for item in FAQ_ITEMS:
        assert "question" in item
        assert item["question"].strip() != ""
        if "links" in item:
            assert "answer" in item
            for link in item["links"]:
                assert "title" in link and "url" in link
        else:
            assert "answer" in item


def test_faq_keyboard():
    keyboard = get_faq_keyboard()
    expected_buttons = sum(1 for item in FAQ_ITEMS if item["question"].strip())
    assert len(keyboard.inline_keyboard) == expected_buttons
    for row in keyboard.inline_keyboard:
        button = row[0]
        assert button.callback_data.startswith("faq_")


# ---------- Тесты для новостей ----------
@pytest.mark.asyncio
async def test_fetch_news_success():
    mock_data = [
        {"title": {"rendered": "Новость 1"}, "link": "https://voenmeh.ru/news1"},
        {"title": {"rendered": "Новость 2"}, "link": "https://voenmeh.ru/news2"},
    ]
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_data)
        mock_get.return_value.__aenter__.return_value = mock_response

        news = await fetch_news()
        assert len(news) == 2
        assert news[0]["title"] == "Новость 1"
        assert news[0]["link"] == "https://voenmeh.ru/news1"


@pytest.mark.asyncio
async def test_fetch_news_error():
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status = 404
        mock_get.return_value.__aenter__.return_value = mock_response

        news = await fetch_news()
        assert news == []


@pytest.mark.asyncio
async def test_fetch_news_exception():
    with patch('aiohttp.ClientSession.get') as mock_get:
        mock_get.side_effect = Exception("Network error")
        news = await fetch_news()
        assert news == []