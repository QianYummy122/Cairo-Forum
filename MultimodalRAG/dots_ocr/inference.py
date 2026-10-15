"""通过 OpenAI 兼容接口调用远程 vLLM 服务进行推理。"""
import requests
from openai import OpenAI

from dots_ocr.utils.image_utils import PILimage_to_base64
from utils.config import CONFIG

_OCR = CONFIG.section("ocr")

#原本我们在本地搭载了vLLM Server（参数啥的都在那边），只不过目前不需要用了（改为用Huggingface 进行本地推理，不使用C/S，记得往项目加Weights文件夹）
def inference_with_vllm(
        image,
        prompt,
        ip=_OCR.get("ip", "localhost"),
        port=_OCR.get("port", 6006),
        temperature=_OCR.get("temperature", 0.1),
        top_p=_OCR.get("top_p", 0.9),
        max_completion_tokens=_OCR.get("max_completion_tokens", 32768),
        model_name=_OCR.get("model_name", "dots_ocr"),
):
    addr = f"http://{ip}:{port}/v1"
    client = OpenAI(api_key=str(_OCR.get("api_key", "0")), base_url=addr)
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": PILimage_to_base64(image)}},
                # 没有 "<|img|><|imgpad|><|endofimg|>" 时，vllm v1 会额外插入 "\n"
                {"type": "text", "text": f"<|img|><|imgpad|><|endofimg|>{prompt}"},
            ],
        }
    ]
    try:
        response = client.chat.completions.create(
            messages=messages,
            model=model_name,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return response.choices[0].message.content
    except requests.exceptions.RequestException as e:
        print(f"request error: {e}")
        return None
