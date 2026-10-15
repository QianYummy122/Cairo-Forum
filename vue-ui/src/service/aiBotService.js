import axios from "axios";

/**
 * 小罗Bot（AI 搜索引擎 Agent）前端服务层。
 *
 * 所有请求都走论坛自己的网关 bbs-rest（`/api/bbs/ai/**`），而不是直连 AI 服务：
 *  - 开发环境由 vue.config.js 把 `/api` 代理到 `http://localhost:7010`，生产同源，
 *    因此不需要任何跨域配置（bbs-rest 也没有配全局 CORS）；
 *  - 统一响应信封 `{code, desc, data}` 与论坛其它接口一致，axios 拦截器里
 *    `code === 0` 才判成功，错误信息取 `err.desc`。
 *
 * 流式对话比较特殊：SSE 不能走 axios（axios 0.21 会把响应整体缓冲，
 * 且拦截器要求响应体是 `{code:0,...}` 的 JSON），所以这里用原生 `fetch`
 * 读取 `ReadableStream`，逐帧解析 `event:` / `data:`。
 */

// SSE 事件名 → 回调名。与后端 agent/events.py 的协议一一对应
const SSE_EVENTS = ["meta", "plan", "agent", "sources", "delta", "done", "error", "end"];

export default {
    // ------------------------------------------------------------------
    // 普通 JSON 接口（走 axios，享受统一信封与错误处理）
    // ------------------------------------------------------------------

    /** 健康检查：模型、知识库、论坛数据源 */
    health() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/health")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 知识库状态 */
    kbStatus() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/kb/status")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 触发论坛知识库同步（后台任务） */
    kbSync(params) {
        return new Promise((resolve, reject) => {
            axios.post("/api/bbs/ai/kb/sync", null, {params})
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 后台同步进度 */
    kbSyncStatus() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/kb/sync/status")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 关于小罗Bot（能力说明） */
    about() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/about")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 会话列表 */
    sessions() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/sessions")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    // ------------------------------------------------------------------
    // 文档附件（仅管理员）
    // ------------------------------------------------------------------

    /** 上传限制：允许的扩展名、大小上限 —— 由服务端下发，前端不重复维护规则 */
    kbUploadLimits() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/kb/upload/limits")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /**
     * 上传文档附件并入库。
     *
     * 用 FormData + onUploadProgress 拿上传进度；服务端收到后立刻返回 taskId，
     * 解析与向量化在后台进行，因此还要再轮询 kbUploadStatus()。
     *
     * @param {File}     file      浏览器 File 对象
     * @param {Function} onProgress (percent: number) => void
     */
    kbUpload(file, onProgress) {
        const form = new FormData();
        form.append("file", file, file.name);
        return new Promise((resolve, reject) => {
            axios.post("/api/bbs/ai/kb/upload", form, {
                headers: {"Content-Type": "multipart/form-data"},
                timeout: 300000,
                onUploadProgress(e) {
                    if (typeof onProgress === "function" && e.total) {
                        onProgress(Math.round((e.loaded * 100) / e.total));
                    }
                },
            })
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 查询附件解析/入库进度 */
    kbUploadStatus(taskId) {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/kb/upload/status/" + taskId)
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 已入库的文档附件列表 */
    kbAttachments() {
        return new Promise((resolve, reject) => {
            axios.get("/api/bbs/ai/kb/attachments")
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 删除某个附件及其知识条目 */
    kbAttachmentDelete(docId) {
        return new Promise((resolve, reject) => {
            axios.delete("/api/bbs/ai/kb/attachments/" + encodeURIComponent(docId))
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    /** 非流式对话（兜底：浏览器不支持流式时使用） */
    chat(data) {
        return new Promise((resolve, reject) => {
            axios.post("/api/bbs/ai/chat", data)
                .then((res) => resolve(res))
                .catch((err) => reject(err));
        });
    },

    // ------------------------------------------------------------------
    // 流式对话（fetch + SSE）
    // ------------------------------------------------------------------

    /**
     * SSE 流式对话。
     *
     * @param {Object}   data      {question, image, sessionId, webSearchEnabled}
     * @param {Object}   handlers  事件回调集合：
     *        onMeta(payload) / onPlan(payload) / onAgent(payload) / onSources(payload)
     *        onDelta(payload) / onDone(payload) / onError(payload) / onEnd()
     * @param {Object}   options   {signal} 用于中断（用户点"停止生成"）
     * @returns {Promise<void>}    流结束时 resolve；被 abort 时也正常 resolve
     */
    chatStream(data, handlers = {}, options = {}) {
        const h = handlers || {};
        const fire = (name, payload) => {
            const fn = h[name];
            if (typeof fn === "function") {
                fn(payload);
            }
        };

        return fetch("/api/bbs/ai/chat/stream", {
            method: "POST",
            headers: {"Content-Type": "application/json", "Accept": "text/event-stream"},
            credentials: "include",
            body: JSON.stringify(data),
            signal: options.signal,
        }).then((response) => {
            if (!response.ok) {
                // 网关自己出错（例如 AI 服务没启动）时返回的是 JSON 错误体
                return response.text().then((text) => {
                    let message = "小罗Bot 服务异常（HTTP " + response.status + "）";
                    try {
                        const body = JSON.parse(text);
                        message = body.desc || body.detail || body.message || message;
                    } catch (e) {
                        // 非 JSON，用默认提示
                    }
                    fire("error", {message});
                    fire("end", {});
                });
            }
            if (!response.body || !response.body.getReader) {
                // 极老的浏览器：退回到非流式
                return this.chat(data).then((res) => {
                    const payload = res.data || {};
                    fire("done", payload);
                    fire("end", {});
                });
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let buffer = "";

            const pump = () => reader.read().then(({done, value}) => {
                if (done) {
                    // 收尾：把残留的最后一帧也解析掉
                    if (buffer.trim()) {
                        parseFrame(buffer, h);
                    }
                    fire("end", {});
                    return;
                }
                buffer += decoder.decode(value, {stream: true});

                // SSE 以空行分帧；兼容 \r\n
                let index;
                while ((index = buffer.search(/\r?\n\r?\n/)) !== -1) {
                    const raw = buffer.slice(0, index);
                    buffer = buffer.slice(index).replace(/^\r?\n\r?\n/, "");
                    parseFrame(raw, h);
                }
                return pump();
            });

            return pump().catch((err) => {
                // 用户主动中断不算错误
                if (err && err.name === "AbortError") {
                    fire("end", {aborted: true});
                    return;
                }
                fire("error", {message: "读取流式响应失败：" + (err && err.message)});
                fire("end", {});
            });
        }).catch((err) => {
            if (err && err.name === "AbortError") {
                fire("end", {aborted: true});
                return;
            }
            fire("error", {message: "无法连接小罗Bot 服务：" + (err && err.message)});
            fire("end", {});
        });
    },
};

/**
 * 解析一个 SSE 帧（可能包含 event: 与 data: 多行），并按事件名回调。
 * 注释帧（以 `:` 开头）是心跳，直接忽略。
 *
 * @param {string} raw    原始帧文本
 * @param {Object} handlers 事件回调集合
 */
function parseFrame(raw, handlers) {
    if (!raw) {
        return;
    }
    let event = "message";
    const dataLines = [];

    raw.split(/\r?\n/).forEach((line) => {
        if (!line || line.startsWith(":")) {
            return;
        }
        if (line.startsWith("event:")) {
            event = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).replace(/^ /, ""));
        }
    });

    if (!SSE_EVENTS.includes(event)) {
        return;
    }
    let payload = {};
    const rawData = dataLines.join("\n");
    if (rawData) {
        try {
            payload = JSON.parse(rawData);
        } catch (e) {
            payload = {text: rawData};
        }
    }

    // end -> onEnd，其它 -> onXxx
    const key = "on" + event.charAt(0).toUpperCase() + event.slice(1);
    const fn = handlers[key];
    if (typeof fn === "function") {
        fn(payload);
    }
}
