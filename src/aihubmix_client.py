from __future__ import annotations

import json
import os
from typing import Any, Literal


AIHUBMIX_BASE_URL = "https://aihubmix.com/v1"
SearchMethod = Literal["none", "web_search_options", "surfing"]


class MissingAIHubMixKey(RuntimeError):
    pass


class AIHubMixSearchError(RuntimeError):
    pass


def has_api_key() -> bool:
    return bool(_read_api_key())


def get_client() -> OpenAI:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise MissingAIHubMixKey("缺少 openai 依赖，请先安装 requirements.txt 后再使用 AIHubMix 模式。") from exc

    api_key = _read_api_key()
    if not api_key:
        raise MissingAIHubMixKey("未检测到 AIHUBMIX_API_KEY，请先配置环境变量。")
    return OpenAI(api_key=api_key, base_url=AIHUBMIX_BASE_URL)


def call_aihubmix_model(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.35,
    enable_search: bool = True,
    search_method: SearchMethod = "web_search_options",
) -> tuple[str, str]:
    client = get_client()
    request_model = f"{model}:surfing" if enable_search and search_method == "surfing" and not model.endswith(":surfing") else model

    kwargs: dict[str, Any] = {
        "model": request_model,
        "messages": messages,
    }

    # Search models and search-enhanced routes may reject sampling parameters.
    if not enable_search:
        kwargs["temperature"] = temperature
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or "", request_model

    if search_method == "surfing":
        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or "", request_model

    try:
        response = client.chat.completions.create(**kwargs, web_search_options={})
        return response.choices[0].message.content or "", request_model
    except TypeError:
        try:
            response = client.chat.completions.create(**kwargs, extra_body={"web_search_options": {}})
            return response.choices[0].message.content or "", request_model
        except Exception as exc:
            raise AIHubMixSearchError(_search_error_message(exc)) from exc
    except Exception as exc:
        raise AIHubMixSearchError(_search_error_message(exc)) from exc


def extract_json_object(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("模型返回的 JSON 不是对象。")
        return payload
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(text[start : end + 1])
            if not isinstance(payload, dict):
                raise ValueError("模型返回的 JSON 不是对象。")
            return payload
        raise


def _search_error_message(exc: Exception) -> str:
    return (
        f"{exc}。可能原因：当前模型不支持联网搜索、模型名称不兼容、"
        "AIHubMix 搜索参数不兼容，或账号没有对应模型/搜索权限。"
    )


def _read_api_key() -> str:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass

    key = os.getenv("AIHUBMIX_API_KEY")
    if key:
        return key.strip()

    if os.name == "nt":
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as env_key:
                value, _ = winreg.QueryValueEx(env_key, "AIHUBMIX_API_KEY")
                return str(value).strip()
        except OSError:
            return ""

    return ""
