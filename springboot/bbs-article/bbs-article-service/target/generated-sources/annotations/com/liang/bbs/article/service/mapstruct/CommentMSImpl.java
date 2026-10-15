package com.liang.bbs.article.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.article.facade.dto.CommentDTO;
import com.liang.bbs.article.persistence.entity.CommentPo;
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
public class CommentMSImpl implements CommentMS {

    @Override
    public CommentDTO toDTO(CommentPo p) {
        if ( p == null ) {
            return null;
        }

        CommentDTO commentDTO = new CommentDTO();

        commentDTO.setId( p.getId() );
        commentDTO.setPreId( p.getPreId() );
        commentDTO.setContent( p.getContent() );
        commentDTO.setArticleId( p.getArticleId() );
        commentDTO.setState( p.getState() );
        commentDTO.setIsDeleted( p.getIsDeleted() );
        commentDTO.setCommentUser( p.getCommentUser() );
        commentDTO.setCreateTime( p.getCreateTime() );
        commentDTO.setUpdateTime( p.getUpdateTime() );

        return commentDTO;
    }

    @Override
    public CommentPo toPo(CommentDTO d) {
        if ( d == null ) {
            return null;
        }

        CommentPo commentPo = new CommentPo();

        commentPo.setId( d.getId() );
        commentPo.setPreId( d.getPreId() );
        commentPo.setContent( d.getContent() );
        commentPo.setArticleId( d.getArticleId() );
        commentPo.setState( d.getState() );
        commentPo.setIsDeleted( d.getIsDeleted() );
        commentPo.setCommentUser( d.getCommentUser() );
        commentPo.setCreateTime( d.getCreateTime() );
        commentPo.setUpdateTime( d.getUpdateTime() );

        return commentPo;
    }

    @Override
    public List<CommentDTO> toDTO(List<CommentPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<CommentDTO> list = new ArrayList<CommentDTO>( pList.size() );
        for ( CommentPo commentPo : pList ) {
            list.add( toDTO( commentPo ) );
        }

        return list;
    }

    @Override
    public List<CommentPo> toPo(List<CommentDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<CommentPo> list = new ArrayList<CommentPo>( pList.size() );
        for ( CommentDTO commentDTO : pList ) {
            list.add( toPo( commentDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<CommentDTO> toPage(PageInfo<CommentPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<CommentDTO> pageInfo1 = new PageInfo<CommentDTO>();

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
