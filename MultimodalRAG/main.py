"""知识库构建 Gradio 界面入口（小罗Bot 的"文档知识"来源之一）。

运行：python main.py
流程：上传 PDF → DotsOCR 解析为 Markdown → 四层分块 → 多模态向量化
      → 写入小罗Bot 的统一知识库 t_knowledge_collection。

注意：论坛内容的知识库不走这里，而是走 ``python -m ingestion.cli sync``
（通过 springboot 网关拉取文章/评论/资源/标签）。两者最终落在同一个集合里，
所以小罗Bot 检索时"论坛内容"和"上传文档"是一起被搜到的。
"""
import os
from typing import Dict, List

import gradio as gr

from dots_ocr.parser import do_parse
from ingestion.forum_ingest import sync_pdf_markdown
from utils.common_utils import delete_directory_if_nonempty, get_filename, get_sorted_md_files
from utils.config import CONFIG
from utils.log_utils import log

# Markdown 解析产物根目录（来自 config.yml -> paths.output_dir）
BASE_MD_DIR = str(CONFIG.path("paths.output_dir"))


class ProcessorAPP:

    def __init__(self):
        self.pdf_path = None
        self.md_dir = None
        self.md_files = None
        self.file_contents = {}

    def upload_pdf(self, pdf_file):
        """处理 PDF 文件的上传。"""
        log.info(f"上传pdf文件：{pdf_file}")
        self.pdf_path = pdf_file if pdf_file else None
        if self.pdf_path:
            return [
                f"PDF已上传: {os.path.basename(self.pdf_path)}",  # status
                gr.Button(interactive=True),
            ]
        return [
            "上传文件没有成功，请重新上传PDF文件",  # status
            gr.Button(interactive=False),
        ]

    def parse_pdf(self):
        """解析 PDF 文件，生成多个 Markdown 文件。"""
        if not self.pdf_path:
            return [
                "请先上传文件！",  # status
                gr.Dropdown(interactive=False),  # file_dropdown
                gr.Button(interactive=True),  # parse_btn
                gr.update(interactive=False),  # save_btn
            ]

        md_files_dir = os.path.join(BASE_MD_DIR, get_filename(self.pdf_path, False))
        delete_directory_if_nonempty(md_files_dir)

        # OCR 解析参数全部来自 config.yml -> ocr
        do_parse(
            input_path=self.pdf_path,
            output=BASE_MD_DIR,
            num_thread=CONFIG.get("ocr.num_thread", 1),
            no_fitz_preprocess=CONFIG.get("ocr.no_fitz_preprocess", True),
            use_hf=CONFIG.get("ocr.use_hf", True),
            dpi=CONFIG.get("ocr.dpi", 120),
            max_pixels=CONFIG.get("ocr.max_pixels"),
        )

        if os.path.isdir(md_files_dir):
            self.md_dir = md_files_dir
            self.md_files = get_sorted_md_files(self.md_dir)
            log.info(f"PDF已解析，生成了{len(self.md_files)}个md文件")

            # 读取所有 md 文件内容以便展示
            for f in self.md_files:
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        self.file_contents[f] = file.read()
                except Exception as e:
                    print(f"读取文件 {f} 时出错: {e}")
                    self.file_contents[f] = f"读取文件内容时出错: {e}"

            file_names = [os.path.basename(f) for f in self.md_files]
            return [
                f"解析完成，共 {len(self.md_files)} 个MD文件",  # status
                gr.Dropdown(choices=file_names, label="MD文件列表", interactive=True),  # file_dropdown
                gr.Button(interactive=False),  # parse_btn
                gr.update(interactive=True),  # save_btn
            ]

        return [
            "解析失败！",  # status
            gr.Dropdown(interactive=False),  # file_dropdown
            gr.Button(interactive=True),  # parse_btn
            gr.update(interactive=False),  # save_btn
        ]

    def select_md_file(self, selected_file):
        """选择一个 md 文件并展示其内容。"""
        log.info(f"选择文件：{selected_file}")
        if not selected_file or not self.md_files:
            return "文件内容加载失败,选择的文件不对"

        for f in self.md_files:
            if os.path.basename(f) == selected_file:
                return self.file_contents.get(f, "没有找到该文件")
        return "没有找到该文件"

    def save_to_knowledge(self):
        """把解析结果存入小罗Bot 的统一知识库。"""
        if not self.md_dir:
            return "请先解析PDF文件"

        result: Dict = sync_pdf_markdown(self.md_dir, self.pdf_path)
        if not result.get("ok"):
            return f"入库失败：{result.get('error')}"

        stats = result.get("stats") or {}
        return (f"成功入库 {result.get('inserted', 0)} 条知识"
                f"（分块 {result.get('chunks', 0)}，向量化 {result.get('embedded', 0)}）；"
                f"当前知识库共 {stats.get('total', 0)} 条")

    def create_interface(self):
        """创建一个构建多模态知识库的界面。"""
        with gr.Blocks() as app:
            gr.Markdown(f"## {CONFIG.get('app.bot_name', '小罗Bot')} · 文档知识库构建")
            gr.Markdown(
                "上传 PDF/图片 → 解析为 Markdown → 四层分块 → 多模态向量化，"
                "写入统一知识库 `t_knowledge_collection`。\n\n"
                "> 论坛内容的知识库请用 `python -m ingestion.cli sync`（走 springboot 网关同步）。"
            )

            with gr.Row():
                pdf_upload = gr.File(label="上传PDF或图片文件",
                                     file_types=['.pdf', '.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp'])
                parse_btn = gr.Button("解析文件", variant="primary", interactive=False)

            status = gr.Textbox(label="状态", value="等待操作...", interactive=False)

            with gr.Row():
                file_dropdown = gr.Dropdown(choices=[], label="MD文件列表", interactive=False)
                content = gr.Textbox(label="文件内容", lines=20, interactive=False)

            save_btn = gr.Button("存入知识库", variant="secondary", interactive=False)

            # 绑定按钮点击事件
            pdf_upload.change(fn=self.upload_pdf, inputs=pdf_upload, outputs=[status, parse_btn])
            parse_btn.click(fn=self.parse_pdf, inputs=[], outputs=[status, file_dropdown, parse_btn, save_btn])
            file_dropdown.change(fn=self.select_md_file, inputs=file_dropdown, outputs=content)
            save_btn.click(fn=self.save_to_knowledge, inputs=[], outputs=status)

        return app


if __name__ == '__main__':
    app = ProcessorAPP()
    interface = app.create_interface()
    interface.launch(
        server_name=CONFIG.get("gradio.server_name", "127.0.0.1"),
        server_port=CONFIG.get("gradio.server_port", 7860),
        share=CONFIG.get("gradio.share", False),
    )
