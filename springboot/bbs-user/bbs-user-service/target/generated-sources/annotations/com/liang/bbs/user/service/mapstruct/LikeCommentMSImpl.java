package com.liang.bbs.user.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.user.facade.dto.LikeCommentDTO;
import com.liang.bbs.user.persistence.entity.LikeCommentPo;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import javax.annotation.processing.Generated;
import org.springframework.stereotype.Component;

@Generated(
    value = "org.mapstruct.ap.MappingProcessor",
    date = "2026-10-12T16:40:54+0800",
    comments = "version: 1.6.3, compiler: javac, environment: Java 17.0.12 (Oracle Corporation)"
)
@Component
public class LikeCommentMSImpl implements LikeCommentMS {

    @Override
    public LikeCommentDTO toDTO(LikeCommentPo p) {
        if ( p == null ) {
            return null;
        }

        LikeCommentDTO likeCommentDTO = new LikeCommentDTO();

        likeCommentDTO.setId( p.getId() );
        likeCommentDTO.setCommentId( p.getCommentId() );
        likeCommentDTO.setState( p.getState() );
        likeCommentDTO.setLikeUser( p.getLikeUser() );
        likeCommentDTO.setCreateTime( p.getCreateTime() );
        likeCommentDTO.setUpdateTime( p.getUpdateTime() );

        return likeCommentDTO;
    }

    @Override
    public LikeCommentPo toPo(LikeCommentDTO d) {
        if ( d == null ) {
            return null;
        }

        LikeCommentPo likeCommentPo = new LikeCommentPo();

        likeCommentPo.setId( d.getId() );
        likeCommentPo.setCommentId( d.getCommentId() );
        likeCommentPo.setState( d.getState() );
        likeCommentPo.setLikeUser( d.getLikeUser() );
        likeCommentPo.setCreateTime( d.getCreateTime() );
        likeCommentPo.setUpdateTime( d.getUpdateTime() );

        return likeCommentPo;
    }

    @Override
    public List<LikeCommentDTO> toDTO(List<LikeCommentPo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LikeCommentDTO> list = new ArrayList<LikeCommentDTO>( pList.size() );
        for ( LikeCommentPo likeCommentPo : pList ) {
            list.add( toDTO( likeCommentPo ) );
        }

        return list;
    }

    @Override
    public List<LikeCommentPo> toPo(List<LikeCommentDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LikeCommentPo> list = new ArrayList<LikeCommentPo>( pList.size() );
        for ( LikeCommentDTO likeCommentDTO : pList ) {
            list.add( toPo( likeCommentDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<LikeCommentDTO> toPage(PageInfo<LikeCommentPo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<LikeCommentDTO> pageInfo1 = new PageInfo<LikeCommentDTO>();

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
