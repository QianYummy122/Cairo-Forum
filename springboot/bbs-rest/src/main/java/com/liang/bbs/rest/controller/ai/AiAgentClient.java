package com.liang.bbs.rest.controller.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.liang.bbs.rest.config.ai.AiAgentProperties;
import com.liang.nansheng.common.enums.ResponseCode;
import com.liang.nansheng.common.web.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.util.LinkedMultiValueMap;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RequestCallback;
import org.springframework.web.client.ResponseExtractor;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Collections;
import java.util.Map;

/**
 * 小罗Bot AI 服务的 HTTP 客户端。
 *
 * <p>为什么要它，而不是让前端直接调 Python 服务：
 * <ol>
 *   <li><b>同源</b>：vue-ui 的 devServer 只代理 {@code /api -> bbs-rest:7010}，
 *       直接访问 {@code 127.0.0.1:7861} 属于跨域，而 bbs-rest 没有全局 CORS 配置，
 *       浏览器会直接拦掉；</li>
 *   <li><b>统一契约</b>：论坛所有接口都返回 {@code {code, desc, data}} 信封，
 *       前端 axios 拦截器依赖 {@code code == 0} 判断成功，走网关才能保持一致；</li>
 *   <li><b>安全与治理</b>：AI 服务只监听内网，登录态、限流、超时、熔断都收敛在网关，
 *       也避免把模型 API Key 所在的服务直接暴露给浏览器。</li>
 * </ol>
 *
 * @author Cairo Forum
 */
@Slf4j
@Component
public class AiAgentClient {

    @Autowired
    private AiAgentProperties properties;

    /**
     * 序列化请求体（RestTemplate 的流式重载要求自己写 RequestCallback）
     */
    @Autowired
    private ObjectMapper objectMapper;

    /**
     * 普通 JSON 请求（同步问答、健康检查、知识库状态等）。
     */
    public JsonNode call(String path, HttpMethod method, Object body) {
        return call(path, method, body, null);
    }

    /**
     * @param path    AI 服务路径，如 {@code /agent/chat}
     * @param method  HTTP 方法
     * @param body    请求体（GET 传 null）
     * @param timeout 覆盖默认读超时（毫秒），null 用配置值
     */
    public JsonNode call(String path, HttpMethod method, Object body, Integer timeout) {
        ensureEnabled();
        String url = buildUrl(path);
        try {
            ResponseEntity<JsonNode> response = restTemplate(timeout)
                    .exchange(url, method, new HttpEntity<>(body, jsonHeaders()), JsonNode.class);
            JsonNode result = response.getBody();
            if (result == null) {
                throw BusinessException.build(ResponseCode.SYSTEM_EXCEPTION, "小罗Bot 返回了空响应");
            }
            return result;
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("[小罗Bot] 调用 AI 服务失败 url={} err={}", url, e.getMessage());
            throw BusinessException.build(ResponseCode.RPC_EXCEPTION,
                    "小罗Bot 服务暂不可用，请确认 AI 服务（MultimodalRAG）已启动：" + e.getMessage());
        }
    }

    /**
     * SSE 流式请求：把上游的字节流原样交给调用方转发给浏览器。
     *
     * <p>这里必须用 {@code execute(..., RequestCallback, ResponseExtractor)}：
     * 只有它能让响应体以 {@code InputStream} 形式增量读取。
     * 用 {@code exchange} 会把整段 SSE 缓冲到内存里，前端就失去"边生成边显示"的意义了。
     *
     * @param path     AI 服务路径，如 {@code /agent/chat/stream}
     * @param body     请求体（会被序列化成 JSON）
     * @param consumer 每读到一段字节就回调一次（由 Controller 写入响应流）
     */
    public void stream(String path, Object body, java.util.function.Consumer<byte[]> consumer) {
        ensureEnabled();
        String url = buildUrl(path);
        // SSE 是长连接：读超时必须按 AI 服务给的预算放开，否则会在生成中途被掐断
        RestTemplate template = restTemplate(properties.getReadTimeout());

        RequestCallback requestCallback = request -> {
            HttpHeaders headers = request.getHeaders();
            headers.setContentType(new MediaType(MediaType.APPLICATION_JSON, StandardCharsets.UTF_8));
            headers.setAccept(Collections.singletonList(MediaType.TEXT_EVENT_STREAM));
            objectMapper.writeValue(request.getBody(), body);
        };

        ResponseExtractor<Void> extractor = response -> {
            try (InputStream in = response.getBody()) {
                byte[] buffer = new byte[1024];
                int len;
                while ((len = in.read(buffer)) != -1) {
                    byte[] chunk = new byte[len];
                    System.arraycopy(buffer, 0, chunk, 0, len);
                    consumer.accept(chunk);
                }
            }
            return null;
        };

        template.execute(url, HttpMethod.POST, requestCallback, extractor);
    }

    /**
     * 上传文件（multipart）到 AI 服务。
     *
     * <p>用 {@code MultiValueMap + FormHttpMessageConverter} 拼 multipart，
     * 由 Spring 的 {@code RestTemplate} 自己写边界；请求体是内存中的字节，
     * 知识库附件最大 20MB（见 {@code ai.agent.upload-max-bytes}），足够。
     *
     * @param path             AI 服务路径，如 {@code /kb/upload}
     * @param fileBytes        文件内容
     * @param originalFilename 原始文件名（AI 服务按扩展名选择解析器）
     * @param queryParams      额外的 query 参数（如 uploader）
     * @param timeout          覆盖读超时（毫秒），null 用配置值
     */
    public JsonNode upload(String path, byte[] fileBytes, String originalFilename,
                           Map<String, Object> queryParams, Integer timeout) {
        ensureEnabled();
        String url = buildUrl(path);
        if (queryParams != null && !queryParams.isEmpty()) {
            UriComponentsBuilder builder = UriComponentsBuilder.fromHttpUrl(url);
            queryParams.forEach((key, value) -> {
                if (value != null) {
                    builder.queryParam(key, value);
                }
            });
            url = builder.build().encode().toUriString();
        }

        MultiValueMap<String, Object> body = new LinkedMultiValueMap<>();
        ByteArrayResource resource = new ByteArrayResource(fileBytes) {
            @Override
            public String getFilename() {
                return originalFilename;
            }
        };
        body.add("file", resource);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.MULTIPART_FORM_DATA);

        try {
            ResponseEntity<JsonNode> response = restTemplate(timeout)
                    .exchange(url, HttpMethod.POST, new HttpEntity<>(body, headers), JsonNode.class);
            JsonNode result = response.getBody();
            if (result == null) {
                throw BusinessException.build(ResponseCode.SYSTEM_EXCEPTION, "小罗Bot 返回了空响应");
            }
            return result;
        } catch (BusinessException e) {
            throw e;
        } catch (Exception e) {
            log.error("[小罗Bot] 上传到 AI 服务失败 url={} err={}", url, e.getMessage());
            throw BusinessException.build(ResponseCode.RPC_EXCEPTION,
                    "小罗Bot 服务暂不可用：" + e.getMessage());
        }
    }

    /**
     * 拼出完整 URL。AI 服务内部路径带前导斜杠，配置里的 base-url 可能带或不带，统一处理。
     */
    private String buildUrl(String path) {
        String base = properties.getBaseUrl() == null ? "" : properties.getBaseUrl().trim();
        while (base.endsWith("/")) {
            base = base.substring(0, base.length() - 1);
        }
        return UriComponentsBuilder.fromHttpUrl(base)
                .path(path.startsWith("/") ? path : "/" + path)
                .build(true)
                .toUriString();
    }

    private void ensureEnabled() {
        if (properties.getEnabled() == null || !properties.getEnabled()) {
            throw BusinessException.build(ResponseCode.OPERATE_FAIL, "小罗Bot 功能当前未启用");
        }
    }

    private HttpHeaders jsonHeaders() {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(new MediaType(MediaType.APPLICATION_JSON, StandardCharsets.UTF_8));
        return headers;
    }

    /**
     * 独立构造 RestTemplate：论坛公共的 RestTemplate 读超时只有 10s（见 bbs-common
     * 的 RestTemplateConfig），而 Agent 一轮动辄十几秒到几分钟，必须单独一份。
     */
    private RestTemplate restTemplate(Integer readTimeout) {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(properties.getConnectTimeout());
        factory.setReadTimeout(readTimeout == null ? properties.getReadTimeout() : readTimeout);
        return new RestTemplate(factory);
    }

    /**
     * 供 Controller 展示用：把 query 参数拼成 Map。
     */
    public static Map<String, Object> params(Object... kv) {
        Map<String, Object> map = new java.util.LinkedHashMap<>();
        for (int i = 0; i + 1 < kv.length; i += 2) {
            if (kv[i + 1] != null) {
                map.put(String.valueOf(kv[i]), kv[i + 1]);
            }
        }
        return map;
    }
}
