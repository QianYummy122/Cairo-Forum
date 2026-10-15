package com.liang.bbs.auth;

import org.apache.dubbo.config.spring.context.annotation.EnableDubbo;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

/**
 * 开罗论坛自托管鉴权/管理服务（替代外部 ns-manage Dubbo 服务）
 *
 * @author bbs-auth
 */
@SpringBootApplication
@EnableDubbo
@EnableScheduling
public class AuthApplication {

    public static void main(String[] args) {
        SpringApplication.run(AuthApplication.class, args);
    }

}
