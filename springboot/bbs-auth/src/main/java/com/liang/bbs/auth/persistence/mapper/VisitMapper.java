package com.liang.bbs.auth.persistence.mapper;

import com.liang.manage.auth.facade.dto.visit.VisitDTO;
import com.liang.manage.auth.facade.dto.visit.VisitSearchDTO;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ns_visit 表 Mapper
 *
 * @author bbs-auth
 */
public interface VisitMapper {

    @Insert("INSERT INTO ns_visit (project_id, ip, country, province, city, host_name, os, `count`, day, title, create_time) " +
            "VALUES (#{projectId}, #{ip}, #{country}, #{province}, #{city}, #{hostName}, #{os}, #{count}, #{day}, #{title}, #{createTime})")
    int insert(VisitDTO visit);

    @Select("SELECT COUNT(*) FROM ns_visit WHERE ip = #{ip} AND project_id = #{projectId} AND create_time >= #{start}")
    long countByIpSince(@Param("ip") String ip, @Param("projectId") Integer projectId, @Param("start") LocalDateTime start);

    @Select("<script>SELECT * FROM ns_visit " +
            "<where>" +
            "<if test='projectId != null'>AND project_id = #{projectId}</if>" +
            "<if test='ip != null and ip != \"\"'>AND ip = #{ip}</if>" +
            "<if test='country != null and country != \"\"'>AND country = #{country}</if>" +
            "<if test='province != null and province != \"\"'>AND province = #{province}</if>" +
            "<if test='city != null and city != \"\"'>AND city = #{city}</if>" +
            "<if test='os != null and os != \"\"'>AND os = #{os}</if>" +
            "</where> ORDER BY create_time DESC</script>")
    List<VisitDTO> selectList(VisitSearchDTO search);

    @Select("SELECT COUNT(*) FROM ns_visit")
    Long countTotal();

    @Select("SELECT * FROM ns_visit ORDER BY create_time DESC LIMIT #{n}")
    List<VisitDTO> selectRecent(@Param("n") Integer n);

    @Select("SELECT country AS title, COUNT(*) AS `count` FROM ns_visit GROUP BY country ORDER BY COUNT(*) DESC")
    List<VisitDTO> statByCountry();

    @Select("SELECT province AS title, COUNT(*) AS `count` FROM ns_visit WHERE country = '中国' GROUP BY province ORDER BY COUNT(*) DESC")
    List<VisitDTO> statByProvince();
}
