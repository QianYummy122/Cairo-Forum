package com.liang.bbs.auth.service.impl;

import com.liang.bbs.auth.persistence.mapper.UserMapper;
import com.liang.bbs.common.facade.server.UserAdminService;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.Collections;
import java.util.List;

/**
 * 用户管理员标识服务实现
 *
 * <p>管理员标识（is_admin）只存在于鉴权库 ns_user 表，由本服务对外提供批量查询。</p>
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class UserAdminServiceImpl implements UserAdminService {

    @Autowired
    private UserMapper userMapper;

    @Override
    public List<Long> listAdminUserIds() {
        List<Long> adminUserIds = userMapper.selectAdminUserIds();
        return adminUserIds == null ? Collections.emptyList() : adminUserIds;
    }
}
