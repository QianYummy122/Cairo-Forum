package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.ArticleDTO;
import com.liang.bbs.article.persistence.entity.ArticlePo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-12T16:41:09+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class ArticleMSImpl implements ArticleMS {

    @Override
    public ArticleDTO toDTO(ArticlePo p) {
        if ( p == null ) {
            return null;
        }

        ArticleDTO articleDTO = new ArticleDTO();

        articleDTO.setId( p.getId() );
        articleDTO.setTitleMap( p.getTitleMap() );
        articleDTO.setTitle( p.getTitle() );
        articleDTO.setContent( p.getContent() );
        articleDTO.setState( p.getState() );
        articleDTO.setPv( p.getPv() );
        articleDTO.setTop( p.getTop() );
        articleDTO.setIsDeleted( p.getIsDeleted() );
        articleDTO.setCreateUser( p.getCreateUser() );
        articleDTO.setUpdateUser( p.getUpdateUser() );
        articleDTO.setCreateTime( p.getCreateTime() );
        articleDTO.setUpdateTime( p.getUpdateTime() );

        return articleDTO;
    }

    @Override
    public ArticlePo toPo(ArticleDTO d) {
        if ( d == null ) {
            return null;
        }

        ArticlePo articlePo = new ArticlePo();

        articlePo.setId( d.getId() );
        articlePo.setTitleMap( d.getTitleMap() );
        articlePo.setTitle( d.getTitle() );
        articlePo.setContent( d.getContent() );
        articlePo.setState( d.getState() );
        articlePo.setPv( d.getPv() );
        articlePo.setTop( d.getTop() );
        articlePo.setIsDeleted( d.getIsDeleted() );
        articlePo.setCreateUser( d.getCreateUser() );
        articlePo.setUpdateUser( d.getUpdateUser() );
        articlePo.setCreateTime( d.getCreateTime() );
        articlePo.setUpdateTime( d.getUpdateTime() );

        return articlePo;
    }

    @Override
    public List<ArticleDTO> toDTO(List<ArticlePo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ArticleDTO> list = new ArrayList<ArticleDTO>( pList.size() );
        for ( ArticlePo articlePo : pList ) {
            list.add( toDTO( articlePo ) );
        }

        return list;
    }

    @Override
    public List<ArticlePo> toPo(List<ArticleDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<ArticlePo> list = new ArrayList<ArticlePo>( pList.size() );
        for ( ArticleDTO articleDTO : pList ) {
            list.add( toPo( articleDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<ArticleDTO> toPage(PageInfo<ArticlePo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<ArticleDTO> pageInfo1 = new PageInfo<ArticleDTO>();

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
