package com.liang.bbs.auth.config;

import org.apache.dubbo.config.spring.context.annotation.DubboComponentScan;
import org.springframework.context.annotation.Configuration;

/**
 * Dubbo 服务扫描配置
 *
 * @author bbs-auth
 */
@Configuration
@DubboComponentScan(basePackages = {"com.liang.bbs.auth.service.impl"})
public class DubboConfig {
}
