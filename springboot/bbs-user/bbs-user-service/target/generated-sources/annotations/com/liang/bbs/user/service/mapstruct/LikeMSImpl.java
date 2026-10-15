package com.liang.bbs.user.service.mapstruct;

import com.github.pagehelper.PageInfo;
import com.liang.bbs.user.facade.dto.LikeDTO;
import com.liang.bbs.user.persistence.entity.LikePo;
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
public class LikeMSImpl implements LikeMS {

    @Override
    public LikeDTO toDTO(LikePo p) {
        if ( p == null ) {
            return null;
        }

        LikeDTO likeDTO = new LikeDTO();

        likeDTO.setId( p.getId() );
        likeDTO.setArticleId( p.getArticleId() );
        likeDTO.setState( p.getState() );
        likeDTO.setLikeUser( p.getLikeUser() );
        likeDTO.setCreateTime( p.getCreateTime() );
        likeDTO.setUpdateTime( p.getUpdateTime() );

        return likeDTO;
    }

    @Override
    public LikePo toPo(LikeDTO d) {
        if ( d == null ) {
            return null;
        }

        LikePo likePo = new LikePo();

        likePo.setId( d.getId() );
        likePo.setArticleId( d.getArticleId() );
        likePo.setState( d.getState() );
        likePo.setLikeUser( d.getLikeUser() );
        likePo.setCreateTime( d.getCreateTime() );
        likePo.setUpdateTime( d.getUpdateTime() );

        return likePo;
    }

    @Override
    public List<LikeDTO> toDTO(List<LikePo> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LikeDTO> list = new ArrayList<LikeDTO>( pList.size() );
        for ( LikePo likePo : pList ) {
            list.add( toDTO( likePo ) );
        }

        return list;
    }

    @Override
    public List<LikePo> toPo(List<LikeDTO> pList) {
        if ( pList == null ) {
            return null;
        }

        List<LikePo> list = new ArrayList<LikePo>( pList.size() );
        for ( LikeDTO likeDTO : pList ) {
            list.add( toPo( likeDTO ) );
        }

        return list;
    }

    @Override
    public PageInfo<LikeDTO> toPage(PageInfo<LikePo> pageInfo) {
        if ( pageInfo == null ) {
            return null;
        }

        PageInfo<LikeDTO> pageInfo1 = new PageInfo<LikeDTO>();

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
