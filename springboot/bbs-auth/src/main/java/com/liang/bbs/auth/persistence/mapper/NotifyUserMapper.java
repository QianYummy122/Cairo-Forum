package com.liang.bbs.auth.persistence.mapper;

import com.liang.manage.auth.facade.dto.notify.NotifyOutDTO;
import com.liang.manage.auth.facade.dto.notify.NotifyUserDTO;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.util.List;

/**
 * ns_notify_user 表 Mapper
 *
 * @author bbs-auth
 */
public interface NotifyUserMapper {

    @Insert("INSERT INTO ns_notify_user (type, notify_id, user_id, is_read, is_deleted, create_user, update_user, create_time, update_time) " +
            "VALUES (#{type}, #{notifyId}, #{userId}, #{isRead}, #{isDeleted}, #{createUser}, #{updateUser}, #{createTime}, #{updateTime})")
    int insert(NotifyUserDTO notifyUser);

    @Insert("<script>INSERT INTO ns_notify_user (type, notify_id, user_id, is_read, is_deleted, create_user, update_user, create_time, update_time) VALUES " +
            "<foreach collection='list' item='nu' separator=','>" +
            "(#{nu.type}, #{nu.notifyId}, #{nu.userId}, #{nu.isRead}, #{nu.isDeleted}, #{nu.createUser}, #{nu.updateUser}, #{nu.createTime}, #{nu.updateTime})" +
            "</foreach></script>")
    int insertBatch(@Param("list") List<NotifyUserDTO> list);

    @Select("SELECT COUNT(*) FROM ns_notify_user nu JOIN ns_notify n ON nu.notify_id = n.id " +
            "WHERE nu.user_id = #{userId} AND nu.is_read = 0 AND nu.is_deleted = 0 AND n.type = #{type} AND n.is_deleted = 0")
    int countNotRead(@Param("userId") Long userId, @Param("type") Integer type);

    @Update("UPDATE ns_notify_user SET is_read = 1 WHERE user_id = #{userId} AND is_deleted = 0 " +
            "AND notify_id IN (SELECT id FROM ns_notify WHERE type = #{type} AND is_deleted = 0)")
    int haveReadAll(@Param("userId") Long userId, @Param("type") Integer type);

    @Update("<script>UPDATE ns_notify_user SET is_read = 1 WHERE user_id = #{userId} AND is_deleted = 0 AND notify_id IN " +
            "<foreach collection='notifyIds' item='nid' open='(' separator=',' close=')'>#{nid}</foreach></script>")
    int markRead(@Param("notifyIds") List<Integer> notifyIds, @Param("userId") Long userId);

    @Select("<script>SELECT nu.notify_id AS id, nu.is_read AS isRead, n.project_id AS projectId, " +
            "n.message AS message, n.type AS type, nu.create_user AS createUser, nu.create_time AS createTime " +
            "FROM ns_notify_user nu " +
            "JOIN ns_notify n ON nu.notify_id = n.id AND n.is_deleted = 0 " +
            "WHERE nu.user_id = #{userId} AND nu.is_deleted = 0 " +
            "<if test='type != null'>AND n.type = #{type}</if> " +
            "<if test='isRead != null'>AND nu.is_read = #{isRead}</if> " +
            "ORDER BY nu.create_time DESC</script>")
    List<NotifyOutDTO> selectOutList(@Param("userId") Long userId, @Param("type") Integer type, @Param("isRead") Boolean isRead);
}
