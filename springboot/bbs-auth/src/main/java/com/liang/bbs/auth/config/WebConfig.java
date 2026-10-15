package com.liang.bbs.auth.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.ResourceHandlerRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

import java.nio.file.Paths;

/**
 * 静态资源映射：将本地上传目录暴露为 /static/** 供文件访问
 *
 * @author bbs-auth
 */
@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Value("${auth.file-storage-path:./uploads}")
    private String fileStoragePath;

    @Override
    public void addResourceHandlers(ResourceHandlerRegistry registry) {
        String absolute = Paths.get(fileStoragePath).toAbsolutePath().normalize().toString();
        registry.addResourceHandler("/static/**")
                .addResourceLocations("file:" + absolute + "/");
    }
}
