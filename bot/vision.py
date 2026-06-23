import json
import base64
import anthropic
import config

_PROMPT = """\
你是一个专业的营养师助手。请分析这张食物照片，识别所有可见的食物，并以 JSON 格式返回结果。

要求：
- 尽可能准确估算每种食物的重量（克）
- 根据重量估算热量和三大营养素
- 如果无法确定，给出合理的中间估计值
- 只返回 JSON，不要其他文字

返回格式：
{
  "foods": [
    {
      "name": "食物名称（中文）",
      "weight_g": 数字,
      "calories": 数字,
      "protein_g": 数字,
      "carbs_g": 数字,
      "fat_g": 数字
    }
  ],
  "total_calories": 数字,
  "total_protein_g": 数字,
  "total_carbs_g": 数字,
  "total_fat_g": 数字,
  "confidence": "high/medium/low",
  "notes": "识别说明或不确定项（可选）"
}"""


def build_vision_prompt() -> str:
    return _PROMPT


def parse_vision_response(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        # parts[1] is the content inside the first ```...``` block
        inner = parts[1]
        if inner.startswith("json"):
            inner = inner[4:]
        text = inner.strip()
    return json.loads(text)


def analyze_food_photo(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    b64 = base64.standard_b64encode(image_bytes).decode()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {"type": "text", "text": build_vision_prompt()},
            ],
        }],
    )
    return parse_vision_response(msg.content[0].text)


def apply_correction(original_data: dict, correction: str) -> dict:
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt = (
        f"原始食物识别结果：\n"
        f"{json.dumps(original_data, ensure_ascii=False, indent=2)}\n\n"
        f"用户修正：{correction}\n\n"
        "请根据用户修正重新计算，以完全相同的 JSON 格式返回完整结果。只返回 JSON，不要其他文字。"
    )
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return parse_vision_response(msg.content[0].text)
