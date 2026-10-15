package com.liang.bbs.user.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.user.facade.dto.UserLevelDTO;
import com.liang.bbs.user.persistence.entity.UserLevelPo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-15T13:49:48+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class UserLevelMSImpl implements UserLevelMS {

    @Override
    public UserLevelDTO toDTO(UserLevelPo p) {
        if ( p == null ) {
            return null;
        }

        UserLevelDTO userLevelDTO = new UserLevelDTO();

        userLevelDTO.setId( p.getId() );
        userLevelDTO.setUserId( p.getUserId() );
        userLevelDTO.setLevel( p.getLevel() );
        userLevelDTO.setPoints( p.getPoints() );
        userLevelDTO.setCreateTime( p.getCreateTime() );
        userLevelDTO.setUpdateTime( p.getUpdateTime() );

        return userLevelDTO;
    }

    @Override
    public UserLevelPo toPo(UserLevelDTO d) {
        if ( d == null ) {
            return null;
        }

        UserLevelPo userLevelPo = new UserLevelPo();

        userLevelPo.setId( d.getId() );
        userLevelPo.setUserId( d.getUserId() );
        userLevelPo.setLevel( d.getLevel() );
        userLevelPo.setPoints( d.getPoints() );
        userLevelPo.setCreateTime( d.getCreateTime() );
        userLevelPo.setUpdateTime( d.getUpdateTime() );

        return userLevelPo;
    }

    @Override
    public List<UserLevelDTO> toDTO(List<UserLevelPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<UserLevelDTO> list = new ArrayList<UserLevelDTO>( pList.size() );
        for ( UserLevelPo userLevelPo : pList ) {
            list.add( toDTO( userLevelPo ) );
        }

        return list;
    }

    @Override
    public List<UserLevelPo> toPo(List<UserLevelDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<UserLevelPo> list = new ArrayList<UserLevelPo>( pList.size() );
        for ( UserLevelDTO userLevelDTO : pList ) {
            list.add( toPo( userLevelDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<UserLevelDTO> toPage(PageInfo<UserLevelPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<UserLevelDTO> pageInfo1 = new PageInfo<UserLevelDTO>();

        pageInfo1.setTotal( pageInfo.getTotal() );
        pageInfo1.setList( toDTO( pageInfo.getList() ) );
        pageInfo1.setPageNum( pageInfo.getPageNum() );
        pageInfo1.setPageSize( pageInfo.getPageSize() );
        pageInfo1.setSize( pageInfo.getSize() );
        pageInfo1.setStartRow( pageInfo.getStartRow() );
        pageInfo1.setEndRow( pageInfo.getEndRow() );
        pageInfo1.setPages( pageInfo.getPages() );
        pageInfo1.setPrePage( pageInfo.getPrePage() );
        pageInfo1.setNextPage( pageInfo.getNextPage() );
        pageInfo1.setIsFirstPage( pageInfo.isIsFirstPage() );
        pageInfo1.setIsLastPage( pageInfo.isIsLastPage() );
        pageInfo1.setHasPreviousPage( pageInfo.isHasPreviousPage() );
        pageInfo1.setHasNextPage( pageInfo.isHasNextPage() );
        pageInfo1.setNavigatePages( pageInfo.getNavigatePages() );
        int[] navigatepageNums = pageInfo.getNavigatepageNums();
        if ( navigatepageNums != null ) {
            pageInfo1.setNavigatepageNums( Arrays.copyOf( navigatepageNums, navigatepageNums.length ) );
        }
        pageInfo1.setNavigateFirstPage( pageInfo.getNavigateFirstPage() );
        pageInfo1.setNavigateLastPage( pageInfo.getNavigateLastPage() );

        return pageInfo1;
    }
}
