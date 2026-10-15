package com.liang.bbs.auth.service.impl;

import com.liang.manage.auth.facade.server.UrlAccessRightService;
import com.liang.nansheng.common.auth.RoleSsoDTO;
import com.liang.nansheng.common.auth.UserSsoDTO;
import com.liang.nansheng.common.enums.RoleGradeEnum;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.stereotype.Component;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * URL 访问权限服务，替代作者 ns-manage 的 UrlAccessRightService
 *
 * <p>规则：未登录 -> 拒绝；超管 -> 放行；非超管 -> 仅拒绝「管理端路径」。
 * 论坛普通接口不设权限，直接放行。
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class UrlAccessRightServiceImpl implements UrlAccessRightService {

    /**
     * 仅超管可访问的管理端路径（相对路径，忽略 /api 上下文）
     */
    private static final Set<String> ADMIN_PATHS = new HashSet<>(Arrays.asList(
            "/bbs/article/updateState",
            "/bbs/article/articleTop",
            "/bbs/article/getPendingReviewArticles",
            "/bbs/article/getDisabledArticles",
            "/bbs/article/getArticleCheckCount",
            "/bbs/label/create",
            "/bbs/label/update",
            "/bbs/label/delete",
            "/bbs/label/uploadLabelLogo",
            "/bbs/resource/create",
            "/bbs/resource/update",
            "/bbs/resource/delete",
            "/bbs/resource/uploadResourceLogo"
    ));

    @Override
    public Boolean checkUrlAccess(UserSsoDTO currentUser, String url, String json) {
        if (currentUser == null) {
            return false;
        }
        if (isSuperAdmin(currentUser)) {
            return true;
        }
        // 非超管：拒绝访问管理端路径
        return !isAdminPath(url);
    }

    private boolean isSuperAdmin(UserSsoDTO user) {
        if (user.getRoles() == null) {
            return false;
        }
        for (RoleSsoDTO role : user.getRoles()) {
            if (RoleGradeEnum.NS_SUPER_ADMIN_ROLE.name().equals(role.getGrade())) {
                return true;
            }
        }
        return false;
    }

    private boolean isAdminPath(String url) {
        if (url == null) {
            return false;
        }
        String path = url;
        int q = path.indexOf('?');
        if (q >= 0) {
            path = path.substring(0, q);
        }
        if (path.startsWith("/api/")) {
            path = path.substring(4);
        }
        for (String admin : ADMIN_PATHS) {
            if (path.equals(admin) || path.startsWith(admin + "/")) {
                return true;
            }
        }
        return false;
    }
}
