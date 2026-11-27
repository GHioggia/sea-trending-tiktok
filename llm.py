"""LLM 统一调用：模型链 fallback，weekly_job 与 translate_data 共用。

- 模型名必须用网关基础名：`[1m]` 等后缀是 Claude Code 的语法（= 基础名 + 1M 上下文
  beta 请求头），直接当 model 字段传给网关会 400 model not found。
- 链条默认 qwen3.8-max → glm-5.3 → qwen3.7-max，可用环境变量 LLM_MODELS 覆盖（逗号分隔）。
- glm-5.3 强制开启 thinking，且网关不认 budget_tokens（实测 thinking 会吃掉几乎全部
  max_tokens 预算）：撞到 enable_thinking 报错时去掉 thinking 参数、把 max_tokens
  放大 4 倍重试，尽量给正文留够空间。
- 全部模型失败时抛出最后一次的异常，由调用方决定降级方式。
"""

import os
import time

import anthropic

# scraper 导入时加载 .env 并装配沙箱合并 CA 包（SSL_CERT_FILE），
# 缺了它 anthropic SDK 过不了 mitmproxy 的 TLS——独立运行 translate_data.py 也依赖这里。
import scraper  # noqa: F401

LLM_MODELS = tuple(
    m.strip()
    for m in os.getenv("LLM_MODELS", "qwen3.8-max,glm-5.3,qwen3.7-max").split(",")
    if m.strip()
)
ATTEMPTS_PER_MODEL = 3
GLM_MAX_TOKENS_FACTOR = 4
GLM_MAX_TOKENS_CAP = 16384

LAST_MODEL = None  # 最近一次成功使用的模型（钉钉留档等用）


def _build_client() -> anthropic.Anthropic:
    kwargs = {}
    base_url = os.environ.get("ANTHROPIC_BASE_URL")
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if base_url and auth_token:
        # ducky 代理要求 Bearer 鉴权（auth_token），不能用 x-api-key
        kwargs = {"base_url": base_url.replace("/v1/anthropic", "/v1"), "auth_token": auth_token}
    return anthropic.Anthropic(**kwargs)


def model_chain(model: str | None = None) -> list[str]:
    """显式指定的模型排最前，其余按默认链顺序兜底"""
    if not model:
        return list(LLM_MODELS)
    return [model] + [m for m in LLM_MODELS if m != model]


def llm_call(prompt: str, max_tokens: int = 1024, model: str | None = None) -> str:
    global LAST_MODEL
    client = _build_client()
    last_err = None
    for m in model_chain(model):
        disable_thinking = True  # 首选关 thinking（省时省钱）；glm-5.3 会拒绝，届时去掉该参数重试
        budget = max_tokens
        for attempt in range(ATTEMPTS_PER_MODEL):
            kwargs = {
                "model": m,
                "max_tokens": budget,
                "messages": [{"role": "user", "content": prompt}],
            }
            if disable_thinking:
                kwargs["thinking"] = {"type": "disabled"}
            try:
                msg = client.messages.create(**kwargs)
                text = "".join(
                    b.text for b in msg.content if getattr(b, "type", None) == "text"
                ).strip()
                if not text:
                    raise RuntimeError(f"空文本响应 stop_reason={msg.stop_reason}")
                LAST_MODEL = m
                return text
            except Exception as e:
                last_err = e
                s = str(e)
                if "model not found" in s:
                    print(f"  [LLM] {m} 未接入，尝试下一个模型")
                    break
                if "enable_thinking" in s and disable_thinking:
                    disable_thinking = False
                    budget = min(max_tokens * GLM_MAX_TOKENS_FACTOR, GLM_MAX_TOKENS_CAP)
                    print(f"  [LLM] {m} 需开启 thinking，去掉参数并放大 max_tokens={budget} 重试")
                    continue
                quota = "429" in s or "Throttling" in s or "quota" in s.lower()
                transient = quota or "空文本响应" in s or "timeout" in s.lower() or "Connection" in s
                if not transient:
                    print(f"  [LLM] {m} 非瞬态错误（{type(e).__name__}），尝试下一个模型")
                    break
                if attempt < ATTEMPTS_PER_MODEL - 1:
                    time.sleep(60 if quota else 3 * (attempt + 1))
    raise last_err
