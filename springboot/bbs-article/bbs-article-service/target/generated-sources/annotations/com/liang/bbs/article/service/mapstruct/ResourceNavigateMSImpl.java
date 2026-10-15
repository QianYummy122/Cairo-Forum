package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.ResourceNavigateDTO;
import com.liang.bbs.article.persistence.entity.ResourceNavigatePo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-12T16:41:10+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class ResourceNavigateMSImpl implements ResourceNavigateMS {

    @Override
    public ResourceNavigateDTO toDTO(ResourceNavigatePo p) {
        if ( p == null ) {
            return null;
        }

        ResourceNavigateDTO resourceNavigateDTO = new ResourceNavigateDTO();

        resourceNavigateDTO.setId( p.getId() );
        resourceNavigateDTO.setResourceName( p.getResourceName() );
        resourceNavigateDTO.setLogo( p.getLogo() );
        resourceNavigateDTO.setCategory( p.getCategory() );
        resourceNavigateDTO.setDesc( p.getDesc() );
        resourceNavigateDTO.setLink( p.getLink() );
        resourceNavigateDTO.setIsDeleted( p.getIsDeleted() );
        resourceNavigateDTO.setCreateUser( p.getCreateUser() );
        resourceNavigateDTO.setUpdateUser( p.getUpdateUser() );
        resourceNavigateDTO.setCreateTime( p.getCreateTime() );
        resourceNavigateDTO.setUpdateTime( p.getUpdateTime() );

        return resourceNavigateDTO;
    }

    @Override
    public ResourceNavigatePo toPo(ResourceNavigateDTO d) {
        if ( d == null ) {
            return null;
        }

        ResourceNavigatePo resourceNavigatePo = new ResourceNavigatePo();

        resourceNavigatePo.setId( d.getId() );
        resourceNavigatePo.setResourceName( d.getResourceName() );
        resourceNavigatePo.setLogo( d.getLogo() );
        resourceNavigatePo.setCategory( d.getCategory() );
        resourceNavigatePo.setDesc( d.getDesc() );
        resourceNavigatePo.setLink( d.getLink() );
        resourceNavigatePo.setIsDeleted( d.getIsDeleted() );
        resourceNavigatePo.setCreateUser( d.getCreateUser() );
        resourceNavigatePo.setUpdateUser( d.getUpdateUser() );
        resourceNavigatePo.setCreateTime( d.getCreateTime() );
        resourceNavigatePo.setUpdateTime( d.getUpdateTime() );

        return resourceNavigatePo;
    }

    @Override
    public List<ResourceNavigateDTO> toDTO(List<ResourceNavigatePo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ResourceNavigateDTO> list = new ArrayList<ResourceNavigateDTO>( pList.size() );
        for ( ResourceNavigatePo resourceNavigatePo : pList ) {
            list.add( toDTO( resourceNavigatePo ) );
        }

        return list;
    }

    @Override
    public List<ResourceNavigatePo> toPo(List<ResourceNavigateDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ResourceNavigatePo> list = new ArrayList<ResourceNavigatePo>( pList.size() );
        for ( ResourceNavigateDTO resourceNavigateDTO : pList ) {
            list.add( toPo( resourceNavigateDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<ResourceNavigateDTO> toPage(PageInfo<ResourceNavigatePo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<ResourceNavigateDTO> pageInfo1 = new PageInfo<ResourceNavigateDTO>();

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
