package com.liang.bbs.rest.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.liang.bbs.rest.config.login.NoNeedLogin;
import com.liang.bbs.rest.config.swagger.ApiVersion;
import com.liang.bbs.rest.config.swagger.ApiVersionConstant;
import com.liang.bbs.rest.controller.ai.AiAgentClient;
import com.liang.bbs.rest.controller.ai.dto.AiChatDTO;
import com.liang.nansheng.common.auth.RoleSsoDTO;
import com.liang.nansheng.common.auth.UserContextUtils;
import com.liang.nansheng.common.auth.UserSsoDTO;
import com.liang.nansheng.common.enums.ResponseCode;
import com.liang.nansheng.common.enums.RoleGradeEnum;
import com.liang.nansheng.common.utils.CommonUtils;
import com.liang.nansheng.common.web.basic.ResponseResult;
import com.liang.nansheng.common.web.exception.BusinessException;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;

/**
 * 小罗Bot（AI 搜索引擎 Agent）接口。
 *
 * <p>这是 vue-ui「小罗Bot」页面唯一的后端入口，浏览器路径为 {@code /api/bbs/ai/**}
 * （{@code server.servlet.context-path=/api} + {@code @RequestMapping("/bbs/ai/")}）。
 *
 * <p>网关在这里做三件事，业务逻辑全部在 AI 服务里：
 * <ol>
 *   <li><b>补齐身份</b>：从 SSO 上下文取当前用户，注入到 AI 请求里，
 *       前端不需要也不能自己声明身份；</li>
 *   <li><b>包统一信封</b>：普通接口返回 {@link ResponseResult}，与论坛其它接口一致；</li>
 *   <li><b>转发 SSE</b>：{@code /chat/stream} 把 AI 服务的 {@code text/event-stream}
 *       原样透传，前端用 fetch + ReadableStream 逐字渲染。</li>
 * </ol>
 *
 * <p>{@code @NoNeedLogin}：未登录用户也能用（以 guest 身份参与知识库检索与长期记忆），
 * 否则前端 axios 拦截器会因为 code=302 直接弹出登录框，页面就没法体验了。
 *
 * @author Cairo Forum
 */
@Slf4j
@RestController
@RequestMapping("/bbs/ai/")
@NoNeedLogin
@Tag(name = "小罗Bot（AI搜索引擎）接口")
public class AiBotController {

    @Autowired
    private AiAgentClient aiAgentClient;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private com.liang.bbs.rest.config.ai.AiAgentProperties aiAgentProperties;

    /**
     * 当前用户信息：登录了就带上，没登录就是访客。
     */
    private Map<String, Object> identity() {
        Map<String, Object> identity = new HashMap<>(4);
        try {
            UserSsoDTO current = UserContextUtils.currentUser();
            if (current != null) {
                identity.put("userId", current.getUserId());
                identity.put("userName", current.getUserName());
            }
        } catch (Exception e) {
            // @NoNeedLogin 下 UserContextUtils 一般可用；个别场景拿不到就按访客处理
            log.debug("[小罗Bot] 获取当前用户失败，按访客处理：{}", e.getMessage());
        }
        if (StringUtils.isBlank((String) identity.get("userName"))) {
            identity.put("userName", "guest");
        }
        return identity;
    }

    // ------------------------------------------------------------------
    // 权限
    // ------------------------------------------------------------------

    /**
     * 当前用户是不是管理员。
     *
     * <p>与前端保持一致的同时略微放宽：前端 {@code store.isManage} 只在角色里出现
     * {@code NS_SUPER_ADMIN_ROLE} 时置真（见 {@code App.vue} 的 getAccess），
     * 这里额外接受 {@code NS_ORDINARY_ADMIN_ROLE}（普通管理员）。
     * 这样"普通管理员看不到按钮、但直接调接口不会被拒"，不会出现
     * "看得见却调不通"的错位，也不构成越权。
     */
    private boolean isAdmin() {
        try {
            UserSsoDTO current = UserContextUtils.currentUser();
            if (current == null || current.getRoles() == null) {
                return false;
            }
            return current.getRoles().stream()
                    .map(RoleSsoDTO::getGrade)
                    .anyMatch(grade -> RoleGradeEnum.NS_SUPER_ADMIN_ROLE.name().equals(grade)
                            || RoleGradeEnum.NS_ORDINARY_ADMIN_ROLE.name().equals(grade));
        } catch (Exception e) {
            log.debug("[小罗Bot] 判断管理员身份失败，按非管理员处理：{}", e.getMessage());
            return false;
        }
    }

    /**
     * 需要管理员才能执行的操作。
     *
     * <p>前端会隐藏入口，但隐藏只是体验层 —— 知道接口地址的人照样能直接 POST，
     * 所以这里必须再挡一道（知识库同步会重建整个向量库并消耗嵌入配额，代价很高）。
     */
    private void requireAdmin(String action) {
        if (!isAdmin()) {
            log.warn("[小罗Bot] 非管理员尝试{}，已拒绝", action);
            throw BusinessException.build(ResponseCode.URL_ACCESS_REFUSED,
                    "只有管理员可以" + action);
        }
    }

    // ------------------------------------------------------------------
    // 对话
    // ------------------------------------------------------------------

    @PostMapping("chat")
    @Operation(summary = "小罗Bot 对话（非流式，一次性返回完整答案）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> chat(@RequestBody AiChatDTO chatDTO) {
        Map<String, Object> payload = new HashMap<>(8);
        payload.put("question", chatDTO.getQuestion());
        payload.put("image", chatDTO.getImage());
        payload.put("sessionId", chatDTO.getSessionId());
        payload.put("webSearchEnabled", Boolean.TRUE.equals(chatDTO.getWebSearchEnabled()));
        payload.putAll(identity());
        return ResponseResult.success(aiAgentClient.call("/agent/chat", HttpMethod.POST, payload));
    }

    /**
     * SSE 流式对话。
     *
     * <p>返回 {@code text/event-stream}，事件序列：
     * {@code meta → plan → agent(start/done) → sources → delta* → done → end}。
     * 前端按事件名分别处理：{@code agent}/{@code plan} 用于渲染"智能体协作过程"，
     * {@code delta} 用于打字机式追加正文，{@code done} 带上引用与统计信息。
     */
    @PostMapping(value = "chat/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "小罗Bot 对话（SSE 流式，实时推送智能体协作过程与回答增量）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public StreamingResponseBody chatStream(@RequestBody AiChatDTO chatDTO) {
        // 身份在进入 SSE 之前就取好：SSE 在异步线程里执行，
        // 那时 ThreadLocal 形式的 UserContextUtils 已经失效了。
        Map<String, Object> identity = identity();

        return (OutputStream outputStream) -> {
            Map<String, Object> payload = new HashMap<>(8);
            payload.put("question", chatDTO.getQuestion());
            payload.put("image", chatDTO.getImage());
            payload.put("sessionId", chatDTO.getSessionId());
            payload.put("webSearchEnabled", Boolean.TRUE.equals(chatDTO.getWebSearchEnabled()));
            payload.putAll(identity);
            try {
                aiAgentClient.stream("/agent/chat/stream", payload, bytes -> {
                    try {
                        outputStream.write(bytes);
                        outputStream.flush();
                    } catch (Exception e) {
                        // 客户端断开是常见情况（用户切页/关标签），不必当成故障
                        throw new IllegalStateException("SSE 写出失败：" + e.getMessage(), e);
                    }
                });
            } catch (Exception e) {
                log.error("[小罗Bot] SSE 转发失败：{}", e.getMessage());
                writeError(outputStream, "小罗Bot 服务暂不可用：" + e.getMessage());
            }
        };
    }

    /**
     * 建流失败时也要按 SSE 协议告诉前端，否则页面会一直转圈。
     */
    private void writeError(OutputStream outputStream, String message) {
        try {
            String data = objectMapper.createObjectNode().put("message", message).toString();
            outputStream.write(("event: error\ndata: " + data + "\n\n").getBytes(StandardCharsets.UTF_8));
            outputStream.write("event: end\ndata: {}\n\n".getBytes(StandardCharsets.UTF_8));
            outputStream.flush();
        } catch (Exception ignored) {
            // 连错误都写不出去就只能放弃了
        }
    }

    // ------------------------------------------------------------------
    // 会话
    // ------------------------------------------------------------------

    @GetMapping("sessions")
    @Operation(summary = "获取当前用户的会话列表")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> sessions() {
        String userName = String.valueOf(identity().get("userName"));
        return ResponseResult.success(aiAgentClient.call(
                "/agent/sessions?userName=" + userName, HttpMethod.GET, null));
    }

    @DeleteMapping("sessions/{sessionId}")
    @Operation(summary = "清理指定会话")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> deleteSession(@PathVariable String sessionId) {
        return ResponseResult.success(aiAgentClient.call(
                "/agent/sessions/" + sessionId, HttpMethod.DELETE, null));
    }

    // ------------------------------------------------------------------
    // 健康检查与知识库
    // ------------------------------------------------------------------

    @GetMapping("health")
    @Operation(summary = "小罗Bot 服务健康检查（模型、知识库、论坛数据源）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> health() {
        return ResponseResult.success(aiAgentClient.call("/health", HttpMethod.GET, null));
    }

    @GetMapping("kb/status")
    @Operation(summary = "知识库状态（条目数、按来源分类、论坛数据源可用性）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbStatus() {
        JsonNode status = aiAgentClient.call("/kb/status", HttpMethod.GET, null);
        // 非管理员看不到内部实现细节：向量集合名（t_knowledge_collection）属于运维信息，
        // 游客/普通用户只需要知道"有多少条知识"就够了。
        // 前端也会按角色隐藏该字段，这里是服务端的第二道保证（隐藏前端拦不住直接调接口）。
        if (status instanceof ObjectNode && !isAdmin()) {
            ((ObjectNode) status).remove("collection");
        }
        return ResponseResult.success(status);
    }

    @PostMapping("kb/sync")
    @Operation(summary = "触发论坛知识库同步（把论坛文章/评论/资源/标签重新索引进向量库，仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbSync(@RequestParam(required = false) String source,
                                           @RequestParam(required = false) Boolean withImages,
                                           @RequestParam(required = false) Boolean async) {
        requireAdmin("同步知识库");
        Map<String, Object> payload = new HashMap<>(4);
        payload.put("source", source);
        payload.put("withImages", withImages == null || withImages);
        // 同步耗时较长，默认走后台任务，避免把 HTTP 连接挂死
        String path = Boolean.FALSE.equals(async) ? "/kb/sync" : "/kb/sync/async";
        return ResponseResult.success(aiAgentClient.call(path, HttpMethod.POST, payload,
                Boolean.FALSE.equals(async) ? null : 30000));
    }

    @GetMapping("kb/sync/status")
    @Operation(summary = "查询后台知识库同步进度（仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbSyncStatus() {
        requireAdmin("查看知识库同步状态");
        return ResponseResult.success(aiAgentClient.call("/kb/sync/status", HttpMethod.GET, null));
    }

    // ------------------------------------------------------------------
    // 文档附件上传（仅管理员）
    // ------------------------------------------------------------------
    // 原先要往知识库加文档得去服务器上跑 python main.py / start_knowledge.ps1，
    // 现在页面上直接传：网关收 multipart → 转给 AI 服务解析入库 → 返回任务号供前端轮询。

    @GetMapping("kb/upload/limits")
    @Operation(summary = "上传限制（允许的扩展名、大小上限、是否仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbUploadLimits() {
        // 这个接口只服务于管理员的上传区，跟着一起做管理员校验，
        // 免得出现"联调桩要求管理员、线上却任何人可读"的错位
        requireAdmin("查看文档上传限制");
        // 限制由 AI 服务的 config.yml 决定，这里透传，避免前端再维护一份规则导致不一致
        return ResponseResult.success(aiAgentClient.call("/kb/upload/limits", HttpMethod.GET, null));
    }

    @PostMapping("kb/upload")
    @Operation(summary = "上传文档附件并入知识库（仅管理员，异步解析）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbUpload(@RequestParam("file") MultipartFile file) throws IOException {
        requireAdmin("上传文档到知识库");
        if (file == null || file.isEmpty()) {
            throw BusinessException.build(ResponseCode.MISSING_PARAMETER_EXCEPTION, "请选择要上传的文件");
        }
        // Servlet 层的上限是 100MB（留给文章配图），文档附件不需要那么大，
        // 先在网关挡住，避免大请求被打进内存再转发给 AI 服务
        Long maxBytes = aiAgentProperties.getUploadMaxBytes();
        if (maxBytes != null && file.getSize() > maxBytes) {
            throw BusinessException.build(ResponseCode.EXCEED_THE_MAX,
                    "文件过大：" + CommonUtils.byteConversion(file.getSize())
                            + "，上限 " + CommonUtils.byteConversion(maxBytes));
        }
        // 上传者用当前登录用户名，写进知识条目的 author 字段，便于溯源与追责
        Map<String, Object> params = new HashMap<>(2);
        params.put("uploader", String.valueOf(identity().get("userName")));

        JsonNode result = aiAgentClient.upload("/kb/upload", file.getBytes(),
                file.getOriginalFilename(), params, null);

        // AI 侧校验不通过（类型/大小）时不抛异常，而是把原因回给前端展示
        if (result.path("accepted").asBoolean(false)) {
            log.info("[小罗Bot] {} 上传附件 {}（{} 字节），taskId={}",
                    identity().get("userName"), file.getOriginalFilename(),
                    file.getSize(), result.path("taskId").asText());
        } else {
            log.info("[小罗Bot] 拒绝附件 {}：{}", file.getOriginalFilename(),
                    result.path("reason").asText());
        }
        return ResponseResult.success(result);
    }

    @GetMapping("kb/upload/status/{taskId}")
    @Operation(summary = "查询附件解析/入库进度（仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbUploadStatus(@PathVariable String taskId) {
        requireAdmin("查看文档入库进度");
        return ResponseResult.success(aiAgentClient.call(
                "/kb/upload/status/" + taskId, HttpMethod.GET, null));
    }

    @GetMapping("kb/attachments")
    @Operation(summary = "已入库的文档附件列表（仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbAttachments() {
        requireAdmin("查看已上传的文档");
        return ResponseResult.success(aiAgentClient.call("/kb/attachments", HttpMethod.GET, null));
    }

    @DeleteMapping("kb/attachments/{docId}")
    @Operation(summary = "删除某个附件及其知识条目（仅管理员）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<JsonNode> kbAttachmentDelete(@PathVariable String docId) {
        requireAdmin("删除已上传的文档");
        return ResponseResult.success(aiAgentClient.call(
                "/kb/attachments/" + docId, HttpMethod.DELETE, null));
    }

    /**
     * 预留：Agent 运行时可观测信息（智能体名单、提示词版本等）。
     * 目前直接透传 AI 服务的健康信息，前端"关于小罗Bot"面板使用。
     */
    @GetMapping("about")
    @Operation(summary = "关于小罗Bot（能力说明，供页面侧栏展示）")
    @ApiVersion(group = ApiVersionConstant.V_300)
    public ResponseResult<ObjectNode> about() {
        ObjectNode node = objectMapper.createObjectNode();
        node.put("name", "小罗Bot");
        node.put("version", "2.0.0");
        node.put("description", "开罗论坛内置的 AI 搜索引擎助手：多智能体协作 + 多模态 RAG，支持按需联网搜索。");
        node.put("agentEndpoint", "/api/bbs/ai/chat/stream");
        node.put("kbStatusEndpoint", "/api/bbs/ai/kb/status");
        node.putArray("adminOnlyEndpoints")
                .add("/api/bbs/ai/kb/sync（同步知识库，仅管理员）")
                .add("/api/bbs/ai/kb/sync/status（同步进度，仅管理员）");
        // 让前端不必重复实现角色判断：非管理员时这些字段会被服务端剔除
        node.put("currentUserIsAdmin", isAdmin());
        node.putArray("capabilities")
                .add("多智能体协作：调度、论坛检索、联网搜索、多模态理解、答案合成、质量评估")
                .add("多模态 RAG：文章正文、图片描述、评论、资源、标签统一检索")
                .add("可选联网搜索：论坛内查不到相关内容时，再获取网络内容作答")
                .add("多轮对话：会话级上下文与长期记忆");
        node.putArray("entryPoints")
                .add("/bot（页面）")
                .add("/api/bbs/ai/chat/stream（SSE）")
                .add("/api/bbs/ai/chat（JSON）");
        return ResponseResult.success(node);
    }
}
