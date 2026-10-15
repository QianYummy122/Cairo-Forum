package com.liang.bbs.rest;

import org.apache.dubbo.config.spring.context.annotation.EnableDubbo;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 论坛对外 Restful API 网关（Dubbo 消费者）
 *
 * @author Qianyummy112
 */
@SpringBootApplication
@EnableDubbo
public class RestApplication {

    public static void main(String[] args) {
        SpringApplication.run(RestApplication.class, args);
    }

}
