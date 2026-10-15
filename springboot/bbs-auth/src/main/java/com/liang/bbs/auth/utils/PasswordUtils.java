package com.liang.bbs.auth.utils;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.UUID;

/**
 * 密码加盐散列工具
 *
 * @author bbs-auth
 */
public final class PasswordUtils {

    private PasswordUtils() {
    }

    /**
     * 生成随机盐值（16 位十六进制）
     */
    public static String generateSalt() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 16);
    }

    /**
     * 散列：SHA256(salt + 明文)
     */
    public static String encrypt(String rawPassword, String salt) {
        try {
            MessageDigest md = MessageDigest.getInstance("SHA-256");
            byte[] digest = md.digest((salt + rawPassword).getBytes(StandardCharsets.UTF_8));
            StringBuilder sb = new StringBuilder();
            for (byte b : digest) {
                sb.append(String.format("%02x", b));
            }
            return sb.toString();
        } catch (Exception e) {
            throw new RuntimeException("密码加密失败", e);
        }
    }

    /**
     * 校验明文密码是否匹配
     */
    public static boolean matches(String rawPassword, String salt, String encrypted) {
        return encrypt(rawPassword, salt).equals(encrypted);
    }
}
