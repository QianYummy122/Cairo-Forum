package com.liang.bbs.auth.config;

import org.mybatis.spring.annotation.MapperScan;
import org.springframework.context.annotation.Configuration;

/**
 * Mybatis 配置
 *
 * @author bbs-auth
 */
@Configuration
@MapperScan(basePackages = {"com.liang.bbs.auth.persistence.mapper"})
public class MybatisConfig {
}
