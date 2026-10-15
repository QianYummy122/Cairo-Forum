package com.liang.bbs.auth.persistence.mapper;

import com.liang.manage.auth.facade.dto.notify.NotifyDTO;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Select;

/**
 * ns_notify 表 Mapper
 *
 * @author bbs-auth
 */
public interface NotifyMapper {

    @Insert("INSERT INTO ns_notify (project_id, message, type, is_deleted) " +
            "VALUES (#{projectId}, #{message}, #{type}, #{isDeleted})")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(NotifyDTO notify);

    @Select("SELECT * FROM ns_notify WHERE id = #{id} AND is_deleted = 0")
    NotifyDTO selectById(Integer id);
}
