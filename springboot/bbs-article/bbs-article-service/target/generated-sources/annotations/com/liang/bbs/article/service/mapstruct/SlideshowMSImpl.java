package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.SlideshowDTO;
import com.liang.bbs.article.persistence.entity.SlideshowPo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-15T13:48:18+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class SlideshowMSImpl implements SlideshowMS {

    @Override
    public SlideshowDTO toDTO(SlideshowPo p) {
        if ( p == null ) {
            return null;
        }

        SlideshowDTO slideshowDTO = new SlideshowDTO();

        slideshowDTO.setId( p.getId() );
        slideshowDTO.setName( p.getName() );
        slideshowDTO.setImage( p.getImage() );
        slideshowDTO.setJumpAddress( p.getJumpAddress() );
        slideshowDTO.setDesc( p.getDesc() );
        slideshowDTO.setState( p.getState() );
        slideshowDTO.setIsDeleted( p.getIsDeleted() );
        slideshowDTO.setCreateUser( p.getCreateUser() );
        slideshowDTO.setUpdateUser( p.getUpdateUser() );
        slideshowDTO.setCreateTime( p.getCreateTime() );
        slideshowDTO.setUpdateTime( p.getUpdateTime() );

        return slideshowDTO;
    }

    @Override
    public SlideshowPo toPo(SlideshowDTO d) {
        if ( d == null ) {
            return null;
        }

        SlideshowPo slideshowPo = new SlideshowPo();

        slideshowPo.setId( d.getId() );
        slideshowPo.setName( d.getName() );
        slideshowPo.setImage( d.getImage() );
        slideshowPo.setJumpAddress( d.getJumpAddress() );
        slideshowPo.setDesc( d.getDesc() );
        slideshowPo.setState( d.getState() );
        slideshowPo.setIsDeleted( d.getIsDeleted() );
        slideshowPo.setCreateUser( d.getCreateUser() );
        slideshowPo.setUpdateUser( d.getUpdateUser() );
        slideshowPo.setCreateTime( d.getCreateTime() );
        slideshowPo.setUpdateTime( d.getUpdateTime() );

        return slideshowPo;
    }

    @Override
    public List<SlideshowDTO> toDTO(List<SlideshowPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<SlideshowDTO> list = new ArrayList<SlideshowDTO>( pList.size() );
        for ( SlideshowPo slideshowPo : pList ) {
            list.add( toDTO( slideshowPo ) );
        }

        return list;
    }

    @Override
    public List<SlideshowPo> toPo(List<SlideshowDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<SlideshowPo> list = new ArrayList<SlideshowPo>( pList.size() );
        for ( SlideshowDTO slideshowDTO : pList ) {
            list.add( toPo( slideshowDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<SlideshowDTO> toPage(PageInfo<SlideshowPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<SlideshowDTO> pageInfo1 = new PageInfo<SlideshowDTO>();

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
