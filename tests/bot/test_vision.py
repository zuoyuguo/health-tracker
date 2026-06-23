import json
import pytest
from bot.vision import parse_vision_response, build_vision_prompt


def test_parse_vision_response_valid_json():
    raw = json.dumps({
        "foods": [{"name": "鸡蛋", "weight_g": 60, "calories": 90,
                   "protein_g": 8, "carbs_g": 0, "fat_g": 6}],
        "total_calories": 90,
        "total_protein_g": 8,
        "total_carbs_g": 0,
        "total_fat_g": 6,
        "confidence": "high",
    })
    result = parse_vision_response(raw)
    assert result["foods"][0]["name"] == "鸡蛋"
    assert result["total_calories"] == 90


def test_parse_vision_response_strips_markdown_code_block():
    raw = '```json\n{"foods": [], "total_calories": 0, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0}\n```'
    result = parse_vision_response(raw)
    assert result["foods"] == []


def test_parse_vision_response_strips_plain_code_block():
    raw = '```\n{"foods": [], "total_calories": 0, "total_protein_g": 0, "total_carbs_g": 0, "total_fat_g": 0}\n```'
    result = parse_vision_response(raw)
    assert result["total_calories"] == 0


def test_parse_vision_response_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_vision_response("这不是 JSON")


def test_build_vision_prompt_contains_required_terms():
    prompt = build_vision_prompt()
    assert "JSON" in prompt
    assert "重量" in prompt
    assert "calories" in prompt or "热量" in prompt
    assert "foods" in prompt
