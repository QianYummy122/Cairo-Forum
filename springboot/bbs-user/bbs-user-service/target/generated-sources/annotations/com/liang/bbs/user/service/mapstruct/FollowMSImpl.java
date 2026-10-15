package com.liang.bbs.user.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.user.facade.dto.FollowDTO;
import com.liang.bbs.user.persistence.entity.FollowPo;
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
public class FollowMSImpl implements FollowMS {

    @Override
    public FollowDTO toDTO(FollowPo p) {
        if ( p == null ) {
            return null;
        }

        FollowDTO followDTO = new FollowDTO();

        followDTO.setId( p.getId() );
        followDTO.setFromUser( p.getFromUser() );
        followDTO.setState( p.getState() );
        followDTO.setToUser( p.getToUser() );
        followDTO.setCreateTime( p.getCreateTime() );
        followDTO.setUpdateTime( p.getUpdateTime() );

        return followDTO;
    }

    @Override
    public FollowPo toPo(FollowDTO d) {
        if ( d == null ) {
            return null;
        }

        FollowPo followPo = new FollowPo();

        followPo.setId( d.getId() );
        followPo.setFromUser( d.getFromUser() );
        followPo.setState( d.getState() );
        followPo.setToUser( d.getToUser() );
        followPo.setCreateTime( d.getCreateTime() );
        followPo.setUpdateTime( d.getUpdateTime() );

        return followPo;
    }

    @Override
    public List<FollowDTO> toDTO(List<FollowPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<FollowDTO> list = new ArrayList<FollowDTO>( pList.size() );
        for ( FollowPo followPo : pList ) {
            list.add( toDTO( followPo ) );
        }

        return list;
    }

    @Override
    public List<FollowPo> toPo(List<FollowDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<FollowPo> list = new ArrayList<FollowPo>( pList.size() );
        for ( FollowDTO followDTO : pList ) {
            list.add( toPo( followDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<FollowDTO> toPage(PageInfo<FollowPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<FollowDTO> pageInfo1 = new PageInfo<FollowDTO>();

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
