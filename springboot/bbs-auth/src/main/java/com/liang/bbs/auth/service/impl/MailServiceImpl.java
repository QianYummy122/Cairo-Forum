package com.liang.bbs.auth.service.impl;

import com.liang.manage.auth.facade.server.MailService;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.mail.SimpleMailMessage;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.stereotype.Component;

import jakarta.mail.internet.MimeMessage;

/**
 * 邮件服务（可选：配置 SMTP 后真实发送，未配置则仅记录日志）
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class MailServiceImpl implements MailService {

    @Autowired(required = false)
    private JavaMailSender mailSender;

    @Override
    public void sendSimpleMail(String to, String subject, String content) {
        if (mailSender == null) {
            log.info("[MAIL][mock] to={} subject={} content={}", to, subject, content);
            return;
        }
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setTo(to);
            message.setSubject(subject);
            message.setText(content);
            mailSender.send(message);
        } catch (Exception e) {
            log.error("发送邮件失败 to={} subject={}", to, subject, e);
        }
    }

    @Override
    public void sendSimpleMail(String to, String subject, String content, String... cc) {
        if (mailSender == null) {
            sendSimpleMail(to, subject, content);
            return;
        }
        try {
            SimpleMailMessage message = new SimpleMailMessage();
            message.setTo(to);
            message.setCc(cc);
            message.setSubject(subject);
            message.setText(content);
            mailSender.send(message);
        } catch (Exception e) {
            log.error("发送邮件失败 to={} subject={}", to, subject, e);
        }
    }

    @Override
    public void sendHtmlMail(String to, String subject, String content) throws Exception {
        sendHtmlMail(to, subject, content, new String[]{});
    }

    @Override
    public void sendHtmlMail(String to, String subject, String content, String... cc) {
        if (mailSender == null) {
            log.info("[MAIL][mock-html] to={} subject={}", to, subject);
            return;
        }
        try {
            MimeMessage message = mailSender.createMimeMessage();
            MimeMessageHelper helper = new MimeMessageHelper(message, true);
            helper.setTo(to);
            if (cc != null && cc.length > 0) {
                helper.setCc(cc);
            }
            helper.setSubject(subject);
            helper.setText(content, true);
            mailSender.send(message);
        } catch (Exception e) {
            log.error("发送HTML邮件失败 to={} subject={}", to, subject, e);
        }
    }

    @Override
    public void sendAttachmentsMail(String to, String subject, String content, String filePath) throws Exception {
        log.info("[MAIL][attachment] to={} subject={} file={}", to, subject, filePath);
    }

    @Override
    public void sendAttachmentsMail(String to, String subject, String content, String filePath, String... cc) {
        log.info("[MAIL][attachment] to={} subject={} file={}", to, subject, filePath);
    }

    @Override
    public void sendResourceMail(String to, String subject, String content, String rscPath, String rscId) throws Exception {
        log.info("[MAIL][resource] to={} subject={}", to, subject);
    }

    @Override
    public void sendResourceMail(String to, String subject, String content, String rscPath, String rscId, String... cc) {
        log.info("[MAIL][resource] to={} subject={}", to, subject);
    }
}
