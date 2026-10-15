package com.liang.bbs.rest.config.ai;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * 小罗Bot（AI 搜索引擎 Agent）相关配置。
 *
 * <p>对应的配置项在 {@code application.yml} 的 {@code ai.agent.*}：
 * <pre>
 * ai:
 *   agent:
 *     enabled: true
 *     base-url: http://127.0.0.1:7861
 *     connect-timeout: 5000
 *     read-timeout: 180000
 * </pre>
 *
 * <p>之所以做成配置项而不是写死：AI 服务（MultimodalRAG 改造而来）与论坛后端
 * 是两个独立部署单元，地址/超时随环境变化，必须可外部覆盖。
 *
 * @author Cairo Forum
 */
@Data
@Configuration
@ConfigurationProperties(prefix = "ai.agent")
public class AiAgentProperties {

    /**
     * 是否启用小罗Bot 接口（关闭后所有 /bbs/ai/** 返回"服务未启用"）
     */
    private Boolean enabled = Boolean.TRUE;

    /**
     * AI 服务地址（MultimodalRAG 的 FastAPI 服务），仅内网可访问
     */
    private String baseUrl = "http://127.0.0.1:7861";

    /**
     * 建立连接超时（毫秒）
     */
    private Integer connectTimeout = 5000;

    /**
     * 读取超时（毫秒）。Agent 一轮要经过规划 + 检索 + 联网 + 生成，给足 3 分钟
     */
    private Integer readTimeout = 180000;

    /**
     * 知识库同步接口的超时（毫秒）。同步要逐条调用嵌入接口，可能很久
     */
    private Integer syncTimeout = 1800000;

    /**
     * 文档附件上传在**网关这一层**的大小上限（字节）。
     *
     * <p>Servlet 层的 multipart 上限是 100MB（见 {@code spring.servlet.multipart}），
     * 那是给文章配图等场景用的。文档附件不需要那么大，这里先挡一道，
     * 避免几十 MB 的请求被打进内存再转发。
     * 真正的类型/大小校验在 AI 服务的 {@code config.yml -> attachment}，
     * 两处的默认值（20MB）保持一致。
     */
    private Long uploadMaxBytes = 20971520L;
}
