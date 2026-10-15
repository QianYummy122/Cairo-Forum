package com.liang.bbs.auth.service.impl;

import com.github.pagehelper.PageHelper;
import com.github.pagehelper.PageInfo;
import com.liang.bbs.auth.persistence.mapper.VisitMapper;
import com.liang.manage.auth.facade.dto.visit.VisitDTO;
import com.liang.manage.auth.facade.dto.visit.VisitSearchDTO;
import com.liang.manage.auth.facade.server.VisitService;
import com.liang.nansheng.common.constant.TimeoutConstants;
import lombok.extern.slf4j.Slf4j;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.List;

/**
 * 访问记录服务，替代作者 ns-manage 的 VisitService
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class VisitServiceImpl implements VisitService {

    @Autowired
    private VisitMapper visitMapper;

    @Override
    public Boolean create(VisitDTO visitDTO) {
        try {
            if (!isIpExpires(visitDTO.getIp(), visitDTO.getProjectId())) {
                // 30 分钟内同一 IP 只记录一次
                return true;
            }
            visitDTO.setCount(1);
            visitDTO.setDay(LocalDate.now().toString());
            visitDTO.setCreateTime(LocalDateTime.now());
            visitMapper.insert(visitDTO);
        } catch (Exception e) {
            log.error("记录访问信息失败", e);
        }
        return true;
    }

    @Override
    public Boolean isIpExpires(String ip, Integer projectId) {
        LocalDateTime start = LocalDateTime.now().minusSeconds(TimeoutConstants.NS_VISIT_TIMEOUT);
        return visitMapper.countByIpSince(ip, projectId, start) == 0;
    }

    @Override
    public PageInfo<VisitDTO> getList(VisitSearchDTO visitSearchDTO) {
        int current = visitSearchDTO.getCurrent() == null ? 1 : visitSearchDTO.getCurrent();
        int size = visitSearchDTO.getSize() == null ? 10 : visitSearchDTO.getSize();
        PageHelper.startPage(current, size);
        return new PageInfo<>(visitMapper.selectList(visitSearchDTO));
    }

    @Override
    public List<VisitDTO> getStatVisitByCountry() {
        return visitMapper.statByCountry();
    }

    @Override
    public List<VisitDTO> getStatVisitByProvince() {
        return visitMapper.statByProvince();
    }

    @Override
    public List<VisitDTO> getRecentVisits(Integer n) {
        return visitMapper.selectRecent(n);
    }

    @Override
    public Long getTotal() {
        Long total = visitMapper.countTotal();
        return total == null ? 0L : total;
    }
}
