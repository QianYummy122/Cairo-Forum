package com.liang.bbs.auth.service.impl;

import com.liang.manage.auth.facade.server.FileService;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.UUID;

/**
 * 文件上传服务（自托管：本地磁盘存储，替代作者七牛云方案）
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class FileServiceImpl implements FileService {

    @Value("${auth.file-storage-path:./uploads}")
    private String storagePath;

    @Value("${auth.file-url-prefix:http://127.0.0.1:7014/static/}")
    private String urlPrefix;

    @Override
    public String fileCutUpload(byte[] bytes, String sourceFileName, String imageType) {
        return upload(bytes, sourceFileName, imageType);
    }

    @Override
    public String fileScaleUpload(byte[] bytes, String sourceFileName, String imageType) {
        return upload(bytes, sourceFileName, imageType);
    }

    private String upload(byte[] bytes, String sourceFileName, String imageType) {
        String ext = getExtension(sourceFileName);
        String filename = UUID.randomUUID().toString().replace("-", "") + ext;
        String subDir = StringUtils.hasText(imageType) ? imageType : "other";
        try {
            Path dir = Paths.get(storagePath, subDir);
            Files.createDirectories(dir);
            Path target = dir.resolve(filename);
            Files.write(target, bytes);
            return urlPrefix + subDir + "/" + filename;
        } catch (IOException e) {
            log.error("文件上传失败", e);
            throw new RuntimeException("文件上传失败", e);
        }
    }

    private String getExtension(String fileName) {
        if (!StringUtils.hasText(fileName) || !fileName.contains(".")) {
            return ".png";
        }
        String ext = fileName.substring(fileName.lastIndexOf('.'));
        return ext.length() > 10 ? ".png" : ext;
    }
}
