package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.ArticleLabelDTO;
import com.liang.bbs.article.persistence.entity.ArticleLabelPo;
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
public class ArticleLabelMSImpl implements ArticleLabelMS {

    @Override
    public ArticleLabelDTO toDTO(ArticleLabelPo p) {
        if ( p == null ) {
            return null;
        }

        ArticleLabelDTO articleLabelDTO = new ArticleLabelDTO();

        articleLabelDTO.setId( p.getId() );
        articleLabelDTO.setArticleId( p.getArticleId() );
        articleLabelDTO.setLabelId( p.getLabelId() );
        articleLabelDTO.setIsDeleted( p.getIsDeleted() );
        articleLabelDTO.setCreateUser( p.getCreateUser() );
        articleLabelDTO.setUpdateUser( p.getUpdateUser() );
        articleLabelDTO.setCreateTime( p.getCreateTime() );
        articleLabelDTO.setUpdateTime( p.getUpdateTime() );

        return articleLabelDTO;
    }

    @Override
    public ArticleLabelPo toPo(ArticleLabelDTO d) {
        if ( d == null ) {
            return null;
        }

        ArticleLabelPo articleLabelPo = new ArticleLabelPo();

        articleLabelPo.setId( d.getId() );
        articleLabelPo.setArticleId( d.getArticleId() );
        articleLabelPo.setLabelId( d.getLabelId() );
        articleLabelPo.setIsDeleted( d.getIsDeleted() );
        articleLabelPo.setCreateUser( d.getCreateUser() );
        articleLabelPo.setUpdateUser( d.getUpdateUser() );
        articleLabelPo.setCreateTime( d.getCreateTime() );
        articleLabelPo.setUpdateTime( d.getUpdateTime() );

        return articleLabelPo;
    }

    @Override
    public List<ArticleLabelDTO> toDTO(List<ArticleLabelPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ArticleLabelDTO> list = new ArrayList<ArticleLabelDTO>( pList.size() );
        for ( ArticleLabelPo articleLabelPo : pList ) {
            list.add( toDTO( articleLabelPo ) );
        }

        return list;
    }

    @Override
    public List<ArticleLabelPo> toPo(List<ArticleLabelDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ArticleLabelPo> list = new ArrayList<ArticleLabelPo>( pList.size() );
        for ( ArticleLabelDTO articleLabelDTO : pList ) {
            list.add( toPo( articleLabelDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<ArticleLabelDTO> toPage(PageInfo<ArticleLabelPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<ArticleLabelDTO> pageInfo1 = new PageInfo<ArticleLabelDTO>();

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
