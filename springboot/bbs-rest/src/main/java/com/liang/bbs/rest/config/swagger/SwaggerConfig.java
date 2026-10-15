package com.liang.bbs.rest.config.swagger;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * @author Qianyummy112
 * @date 2021-04-20 22:39
 */
@Configuration
public class SwaggerConfig {

    /**
     * 文档首页概述
     *
     * @return
     */
    @Bean
    public OpenAPI openAPI() {
        return new OpenAPI()
                .info(new Info()
                        .title("开罗论坛（Cairo Forum）Restful API 文档")
                        .version(ApiVersionConstant.V_LATEST)
                        .description("开罗论坛后端接口文档：涵盖文章、评论、标签、资源导航、"
                                + "用户与鉴权，以及小罗Bot（AI 搜索引擎）相关接口。")
                        .contact(new Contact().name("Qianyummy112")
                                .url("https://github.com/QianYummy122/Cairo-Forum")
                                .email("924818949@qq.com")));
    }

//    @Bean
//    public GroupedOpenApi publicApi() {
//        return GroupedOpenApi.builder()
//                .group("default")
//                .pathsToMatch("/api/**")
//                .build();
//    }


}
