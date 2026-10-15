/**
 * 小罗Bot 聊天区的 Markdown 渲染工具。
 *
 * 为什么不用 mavon-editor：它是一个完整的编辑器组件，每条消息挂一个实例在
 * 流式输出时开销很大（每次 delta 都要重新渲染整篇），而且它导出的
 * `markdownIt` 在 2.10.4 里是 null（内部 mixin 的 data 只在 created 时才初始化），
 * 拿不到独立的渲染器。所以这里用轻量的 `marked`，配合自定义的
 * `.markdown-body` 样式（见 BotChat.vue），只负责"把回答显示好看"。
 */
import marked from "marked";

// marked v4 的同步渲染；关闭 mangle 以免邮箱被转义得看不懂
marked.setOptions({
    gfm: true,          // 支持表格、任务列表、删除线
    breaks: true,       // 单个换行也换行，符合聊天场景的直觉
    headerIds: false,
    mangle: false,
});

/**
 * 把 Markdown 渲染成 HTML 字符串。
 * 渲染异常时退化为纯文本（转义后按 <br> 换行），保证聊天区永远不空白。
 */
export function renderMarkdown(text) {
    if (!text) {
        return "";
    }
    try {
        return marked.parse(String(text));
    } catch (e) {
        return escapeHtml(text).replace(/\n/g, "<br>");
    }
}

/** HTML 转义（用于纯文本兜底） */
export function escapeHtml(text) {
    return String(text == null ? "" : text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

/**
 * 论坛站内的引用链接需要按路由跳转，外链则新窗口打开。
 * 这里把 Markdown 里的链接统一补上 target/rel，并给站内链接加样式类。
 */
export function decorateLinks(html) {
    if (!html) {
        return "";
    }
    return html.replace(/<a\s+href="([^"]*)"/g, (match, href) => {
        const internal = href.startsWith("/") || href.startsWith("#");
        const target = internal ? "" : ' target="_blank" rel="noopener noreferrer"';
        const cls = internal ? "bot-link-internal" : "bot-link-external";
        return `<a class="${cls}" href="${href}"${target}`;
    });
}

export default {renderMarkdown, escapeHtml, decorateLinks};
