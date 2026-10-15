"""小罗Bot 多智能体问答的 Gradio 调试界面（Web 正式页面在 vue-ui 的 /bot）。

运行：python graph/workflow_gradio.py
用途：不启动 springboot / vue 的情况下，单独调试 Agent 与知识库。

与旧版的区别：这个界面现在是**薄壳**——它只负责渲染，
真正干活的是 ``agent/`` 里的多智能体图（与 vue-ui 页面完全同一套 Agent），
所以在这里调通的行为，正式页面上的表现是一致的。
"""
import os
import sys
from typing import Dict, List

# 保证作为脚本直接运行时也能 import 项目内模块
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import gradio as gr
from langchain_core.messages import HumanMessage

from agent.session import stream_chat
from utils.config import CONFIG
from utils.log_utils import log

CSS = """
#bot-header {background: linear-gradient(120deg, #FFF8E6 0%, #FDF1D6 55%, #FAE9C4 100%);
             border-radius: 10px; padding: 10px 16px;}
#bot-header h2 {margin: 0; color: #3D3A34;}
#bot-header p {margin: 4px 0 0; color: #8B8272; font-size: 13px;}
.bot-trace {font-family: monospace; font-size: 12px; color: #6B6558;}
"""


def format_trace(plan: List[str], trace: List[Dict]) -> str:
    """把智能体协作轨迹渲染成 Markdown（侧栏展示）。"""
    lines = []
    if plan:
        lines.append(f"**执行计划**：{' → '.join(plan)}\n")
    if not trace:
        return "\n".join(lines) or "_（还没有开始）_"
    for item in trace:
        lines.append(f"- **{item.get('label') or item.get('agent')}** · {item.get('action')}："
                     f"{item.get('detail') or ''}")
    return "\n".join(lines)


def build_ui():
    with gr.Blocks(title=CONFIG.get("app.title", "小罗Bot")) as demo:
        gr.HTML(
            "<div id='bot-header'>"
            f"<h2>🏖️ {CONFIG.get('app.bot_name', '小罗Bot')} · AI 搜索引擎</h2>"
            "<p>多智能体协作 + 多模态 RAG：先查开罗论坛，查不到再联网。<br/>"
            "这是调试界面；正式入口在论坛网页的 <code>/bot</code> 页面。</p>"
            "</div>"
        )

        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(label="对话", height=460, render_markdown=True, line_breaks=False)
                with gr.Row():
                    textbox = gr.Textbox(placeholder="问点什么吧…（Enter 发送）",
                                         show_label=False, scale=5, lines=1)
                    web_toggle = gr.Checkbox(
                        label="联网搜索",
                        value=bool(CONFIG.get("web_search.enabled_by_default", False)),
                        scale=1,
                    )
                with gr.Row():
                    send_btn = gr.Button("发送", variant="primary")
                    clear_btn = gr.Button("新对话")

            with gr.Column(scale=2):
                trace_box = gr.Markdown("_（还没有开始）_", elem_classes=["bot-trace"], label="智能体协作过程")
                status_box = gr.Markdown("")

        state = gr.State({"sessionId": None})

        async def respond(message, history, web_enabled, session_state):
            """一次问答：把事件流翻译成 Gradio 的增量输出。"""
            history = history or []
            session_state = session_state or {"sessionId": None}

            if not (message or "").strip():
                yield history, trace_box.value, "请输入内容", session_state
                return

            history = history + [{"role": "user", "content": message},
                                 {"role": "assistant", "content": ""}]
            answer, plan, trace, status = "", [], [], ""
            yield history, "_正在调度智能体…_", "", session_state

            async for event in stream_chat(
                question=message,
                session_id=session_state.get("sessionId"),
                user=CONFIG.get("workflow.user_name", "guest"),
                web_search_enabled=bool(web_enabled),
            ):
                kind, data = event["event"], event["data"]
                if kind == "meta":
                    session_state = {"sessionId": data.get("sessionId")}
                elif kind == "plan":
                    plan = data.get("plan") or []
                elif kind == "agent":
                    if data.get("status") == "start":
                        trace.append({"label": data.get("label"), "action": "开始",
                                      "detail": data.get("detail") or ""})
                    else:
                        trace.append({"label": data.get("label"), "action": data.get("status"),
                                      "detail": data.get("detail") or ""})
                elif kind == "delta":
                    answer += data.get("text") or ""
                    history[-1]["content"] = answer
                    yield history, format_trace(plan, trace), status, session_state
                elif kind == "done":
                    answer = data.get("answer") or answer
                    history[-1]["content"] = answer
                    status = (f"论坛命中充分：{data.get('forumSufficient')} ｜ "
                              f"相似度：{data.get('forumRelevance')} ｜ "
                              f"联网：{data.get('usedWebSearch')} ｜ "
                              f"质量分：{data.get('answerScore')} ｜ "
                              f"耗时：{data.get('elapsedMs')} ms")
                elif kind == "error":
                    status = f"❌ {data.get('message')}"
                    if not answer:
                        history[-1]["content"] = status

            yield history, format_trace(plan, trace), status, session_state

        def reset():
            return [], "_（还没有开始）_", "", {"sessionId": None}

        send_btn.click(respond, [textbox, chatbot, web_toggle, state],
                       [chatbot, trace_box, status_box, state]).then(
            lambda: "", None, textbox)
        textbox.submit(respond, [textbox, chatbot, web_toggle, state],
                       [chatbot, trace_box, status_box, state]).then(
            lambda: "", None, textbox)
        clear_btn.click(reset, None, [chatbot, trace_box, status_box, state])

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch(
        debug=CONFIG.get("gradio.debug", True),
        server_name=CONFIG.get("gradio.server_name", "127.0.0.1"),
        server_port=CONFIG.get("gradio.server_port", 7860),
        share=CONFIG.get("gradio.share", False),
        theme=gr.themes.Soft(),
        css=CSS,
        allowed_paths=[PROJECT_ROOT],
    )
