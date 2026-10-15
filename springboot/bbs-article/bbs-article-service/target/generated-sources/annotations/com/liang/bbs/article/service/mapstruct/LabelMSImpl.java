package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.LabelDTO;
import com.liang.bbs.article.persistence.entity.LabelPo;
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
public class LabelMSImpl implements LabelMS {

    @Override
    public LabelDTO toDTO(LabelPo p) {
        if ( p == null ) {
            return null;
        }

        LabelDTO labelDTO = new LabelDTO();

        labelDTO.setId( p.getId() );
        labelDTO.setLabelName( p.getLabelName() );
        labelDTO.setLogo( p.getLogo() );
        labelDTO.setIsDeleted( p.getIsDeleted() );
        labelDTO.setCreateUser( p.getCreateUser() );
        labelDTO.setUpdateUser( p.getUpdateUser() );
        labelDTO.setCreateTime( p.getCreateTime() );
        labelDTO.setUpdateTime( p.getUpdateTime() );

        return labelDTO;
    }

    @Override
    public LabelPo toPo(LabelDTO d) {
        if ( d == null ) {
            return null;
        }

        LabelPo labelPo = new LabelPo();

        labelPo.setId( d.getId() );
        labelPo.setLabelName( d.getLabelName() );
        labelPo.setLogo( d.getLogo() );
        labelPo.setIsDeleted( d.getIsDeleted() );
        labelPo.setCreateUser( d.getCreateUser() );
        labelPo.setUpdateUser( d.getUpdateUser() );
        labelPo.setCreateTime( d.getCreateTime() );
        labelPo.setUpdateTime( d.getUpdateTime() );

        return labelPo;
    }

    @Override
    public List<LabelDTO> toDTO(List<LabelPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LabelDTO> list = new ArrayList<LabelDTO>( pList.size() );
        for ( LabelPo labelPo : pList ) {
            list.add( toDTO( labelPo ) );
        }

        return list;
    }

    @Override
    public List<LabelPo> toPo(List<LabelDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LabelPo> list = new ArrayList<LabelPo>( pList.size() );
        for ( LabelDTO labelDTO : pList ) {
            list.add( toPo( labelDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<LabelDTO> toPage(PageInfo<LabelPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<LabelDTO> pageInfo1 = new PageInfo<LabelDTO>();

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
