package com.liang.bbs.user.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.user.facade.dto.DynamicDTO;
import com.liang.bbs.user.persistence.entity.DynamicPo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-12T16:40:53+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class DynamicMSImpl implements DynamicMS {

    @Override
    public DynamicDTO toDTO(DynamicPo p) {
        if ( p == null ) {
            return null;
        }

        DynamicDTO dynamicDTO = new DynamicDTO();

        dynamicDTO.setId( p.getId() );
        dynamicDTO.setType( p.getType() );
        dynamicDTO.setUserId( p.getUserId() );
        dynamicDTO.setObjectId( p.getObjectId() );
        dynamicDTO.setCommentId( p.getCommentId() );
        dynamicDTO.setCreateTime( p.getCreateTime() );
        dynamicDTO.setUpdateTime( p.getUpdateTime() );

        return dynamicDTO;
    }

    @Override
    public DynamicPo toPo(DynamicDTO d) {
        if ( d == null ) {
            return null;
        }

        DynamicPo dynamicPo = new DynamicPo();

        dynamicPo.setId( d.getId() );
        dynamicPo.setType( d.getType() );
        dynamicPo.setUserId( d.getUserId() );
        dynamicPo.setObjectId( d.getObjectId() );
        dynamicPo.setCommentId( d.getCommentId() );
        dynamicPo.setCreateTime( d.getCreateTime() );
        dynamicPo.setUpdateTime( d.getUpdateTime() );

        return dynamicPo;
    }

    @Override
    public List<DynamicDTO> toDTO(List<DynamicPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<DynamicDTO> list = new ArrayList<DynamicDTO>( pList.size() );
        for ( DynamicPo dynamicPo : pList ) {
            list.add( toDTO( dynamicPo ) );
        }

        return list;
    }

    @Override
    public List<DynamicPo> toPo(List<DynamicDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<DynamicPo> list = new ArrayList<DynamicPo>( pList.size() );
        for ( DynamicDTO dynamicDTO : pList ) {
            list.add( toPo( dynamicDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<DynamicDTO> toPage(PageInfo<DynamicPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<DynamicDTO> pageInfo1 = new PageInfo<DynamicDTO>();

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
