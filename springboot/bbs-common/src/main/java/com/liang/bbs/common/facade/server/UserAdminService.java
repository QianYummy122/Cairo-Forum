package com.liang.bbs.common.facade.server;

import java.util.List;

/**
 * 用户管理员标识服务
 *
 * <p>管理员标识（ns_user.is_admin）仅存在于鉴权库，由 bbs-auth 提供实现，
 * 其它服务 / bbs-rest 通过该 Dubbo 接口获取管理员用户 id，用于前端头像等处的“会员/管理员”标识展示。</p>
 *
 * @author bbs-auth
 */
public interface UserAdminService {

    /**
     * 查询所有管理员的用户 id 列表
     *
     * @return 管理员（is_admin = 1）的用户 id 集合
     */
    List<Long> listAdminUserIds();
}
