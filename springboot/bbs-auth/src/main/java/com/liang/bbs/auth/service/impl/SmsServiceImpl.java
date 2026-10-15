package com.liang.bbs.auth.service.impl;

import com.aliyuncs.dysmsapi.model.v20170525.SendSmsResponse;
import com.liang.manage.auth.facade.server.SmsService;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

/**
 * 短信服务（可选：配置阿里云 AK 后真实发送，未配置则仅记录日志）
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class SmsServiceImpl implements SmsService {

    @Value("${auth.sms.access-key-id:}")
    private String accessKeyId;

    @Value("${auth.sms.access-key-secret:}")
    private String accessKeySecret;

    @Value("${auth.sms.sign-name:}")
    private String signName;

    @Value("${auth.sms.template-code:}")
    private String templateCode;

    @Override
    public SendSmsResponse sendSms(String phone, String code) {
        SendSmsResponse response = new SendSmsResponse();
        if (!StringUtils.hasText(accessKeyId) || !StringUtils.hasText(accessKeySecret)) {
            // 自托管未配置短信：仅打印，验证码已写入 Redis（见 UserServiceImpl）
            log.info("[SMS][mock] phone={} code={} sign={} template={}", phone, code, signName, templateCode);
            response.setCode("OK");
            response.setMessage("self-hosted mock sms");
            return response;
        }
        // TODO: 接入阿里云短信（配置 auth.sms.* 后在此实现真实发送）
        log.warn("短信服务尚未接入阿里云，请配置 auth.sms.* 并实现真实发送。phone={} code={}", phone, code);
        response.setCode("OK");
        response.setMessage("not implemented");
        return response;
    }
}
