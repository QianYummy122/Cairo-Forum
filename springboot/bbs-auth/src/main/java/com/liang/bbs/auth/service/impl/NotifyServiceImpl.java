package com.liang.bbs.auth.service.impl;

import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import com.liang.bbs.auth.persistence.mapper.NotifyMapper;
import com.liang.bbs.auth.persistence.mapper.NotifyUserMapper;
import com.liang.manage.auth.facade.dto.notify.NotifyDTO;
import com.liang.manage.auth.facade.dto.notify.NotifyOutDTO;
import com.liang.manage.auth.facade.dto.notify.NotifySearchDTO;
import com.liang.manage.auth.facade.dto.notify.NotifyUserDTO;
import com.liang.manage.auth.facade.server.NotifyService;
import com.liang.nansheng.common.auth.UserSsoDTO;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.collections4.CollectionUtils;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 通知服务，替代作者 ns-manage 的 NotifyService
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class NotifyServiceImpl implements NotifyService {

    @Autowired
    private NotifyMapper notifyMapper;

    @Autowired
    private NotifyUserMapper notifyUserMapper;

    @Override
    public Boolean create(NotifyDTO notifyDTO, List<Long> needNotifyUserIds, UserSsoDTO currentUser) {
        notifyDTO.setIsDeleted(false);
        notifyMapper.insert(notifyDTO);
        if (CollectionUtils.isNotEmpty(needNotifyUserIds)) {
            LocalDateTime now = LocalDateTime.now();
            List<NotifyUserDTO> list = new ArrayList<>();
            for (Long userId : needNotifyUserIds) {
                NotifyUserDTO nu = new NotifyUserDTO();
                nu.setType(notifyDTO.getType());
                nu.setNotifyId(notifyDTO.getId());
                nu.setUserId(userId);
                nu.setIsRead(false);
                nu.setIsDeleted(false);
                nu.setCreateUser(currentUser == null ? null : currentUser.getUserId());
                nu.setUpdateUser(currentUser == null ? null : currentUser.getUserId());
                nu.setCreateTime(now);
                nu.setUpdateTime(now);
                list.add(nu);
            }
            notifyUserMapper.insertBatch(list);
        }
        return true;
    }

    @Override
    public Integer getNotReadNotifyCount(Long userId, Integer type) {
        return notifyUserMapper.countNotRead(userId, type);
    }

    @Override
    public Boolean haveRead(UserSsoDTO currentUser, Integer type) {
        return notifyUserMapper.haveReadAll(currentUser.getUserId(), type) >= 0;
    }

    @Override
    public Boolean markRead(List<Integer> notifyIds, UserSsoDTO currentUser) {
        if (CollectionUtils.isEmpty(notifyIds)) {
            return true;
        }
        return notifyUserMapper.markRead(notifyIds, currentUser.getUserId()) >= 0;
    }

    @Override
    public PageInfo<NotifyOutDTO> getList(NotifySearchDTO notifySearchDTO, UserSsoDTO currentUser) {
        int current = notifySearchDTO.getCurrent() == null ? 1 : notifySearchDTO.getCurrent();
        int size = notifySearchDTO.getSize() == null ? 10 : notifySearchDTO.getSize();
        PageHelper.startPage(current, size);
        List<NotifyOutDTO> list = notifyUserMapper.selectOutList(currentUser.getUserId(),
                notifySearchDTO.getType(), notifySearchDTO.getIsRead());
        return new PageInfo<>(list);
    }
}
