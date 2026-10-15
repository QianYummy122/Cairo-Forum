package com.liang.bbs.rest.controller.ai.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.Data;

import java.io.Serializable;

/**
 * 小罗Bot 对话请求。
 *
 * <p>由前端「小罗Bot」页面（vue-ui 的 BotChat 组件）发起，
 * 经 bbs-rest 透传给 AI 服务。{@code userId}/{@code userName} 由网关从 SSO
 * 上下文补齐，前端不需要（也不应该）自己传，避免伪造身份。
 *
 * @author Cairo Forum
 */
@Data
@Schema(name = "AiChatDTO", description = "小罗Bot 对话请求")
public class AiChatDTO implements Serializable {

    @Schema(description = "用户问题（纯文本）")
    private String question;

    @Schema(description = "图片：data URI（前端 FileReader 读出的 base64）或 http(s) 图片地址")
    private String image;

    @Schema(description = "会话 id；不传则开启新会话")
    private String sessionId;

    @Schema(description = "是否启用联网搜索。关闭时只在论坛知识库中检索；"
            + "开启后若论坛查不到相关内容，则联网检索后再作答")
    private Boolean webSearchEnabled = Boolean.FALSE;

    private static final long serialVersionUID = 1L;
}
