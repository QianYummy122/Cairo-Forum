package com.liang.bbs.auth.persistence.mapper;

import com.liang.manage.auth.facade.dto.user.UserDTO;
import com.liang.manage.auth.facade.dto.user.UserListDTO;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Options;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;
import java.util.List;

/**
 * ns_user 表 Mapper
 *
 * @author bbs-auth
 */
public interface UserMapper {

    @Select("SELECT * FROM ns_user WHERE id = #{id}")
    UserDTO selectById(Long id);

    @Select("<script>SELECT * FROM ns_user WHERE id IN " +
            "<foreach collection='list' item='id' open='(' separator=',' close=')'>#{id}</foreach></script>")
    List<UserDTO> selectByIds(List<Long> ids);

    @Select("SELECT * FROM ns_user WHERE name = #{name} LIMIT 1")
    UserDTO selectByName(String name);

    @Select("SELECT * FROM ns_user WHERE phone = #{phone} LIMIT 1")
    UserDTO selectByPhone(String phone);

    @Select("SELECT * FROM ns_user WHERE email = #{email} LIMIT 1")
    UserDTO selectByEmail(String email);

    @Select("SELECT * FROM ns_user WHERE auth_id = #{authId} AND auth_source = #{authSource} LIMIT 1")
    UserDTO selectByAuth(@Param("authId") String authId, @Param("authSource") String authSource);

    @Select("SELECT is_admin FROM ns_user WHERE id = #{id}")
    Boolean selectIsAdmin(Long id);

    @Select("SELECT id FROM ns_user WHERE is_admin = 1")
    List<Long> selectAdminUserIds();

    @Insert("INSERT INTO ns_user (name, password, salt, gender, birthday, phone, email, picture, position, company, home_page, intro, org_id, state, auth_id, auth_source, is_admin, create_time, update_time) " +
            "VALUES (#{name}, #{password}, #{salt}, #{gender}, #{birthday}, #{phone}, #{email}, #{picture}, #{position}, #{company}, #{homePage}, #{intro}, #{orgId}, #{state}, #{authId}, #{authSource}, 0, #{createTime}, #{updateTime})")
    @Options(useGeneratedKeys = true, keyProperty = "id")
    int insert(UserDTO user);

    @Update("<script>UPDATE ns_user <set>" +
            "<if test='name != null and name != \"\"'>name = #{name},</if>" +
            "<if test='password != null'>password = #{password},</if>" +
            "<if test='salt != null'>salt = #{salt},</if>" +
            "<if test='gender != null'>gender = #{gender},</if>" +
            "<if test='birthday != null'>birthday = #{birthday},</if>" +
            "<if test='phone != null'>phone = #{phone},</if>" +
            "<if test='email != null'>email = #{email},</if>" +
            "<if test='picture != null'>picture = #{picture},</if>" +
            "<if test='position != null'>position = #{position},</if>" +
            "<if test='company != null'>company = #{company},</if>" +
            "<if test='homePage != null'>home_page = #{homePage},</if>" +
            "<if test='intro != null'>intro = #{intro},</if>" +
            "<if test='orgId != null'>org_id = #{orgId},</if>" +
            "<if test='state != null'>state = #{state},</if>" +
            "<if test='authId != null'>auth_id = #{authId},</if>" +
            "<if test='authSource != null'>auth_source = #{authSource},</if>" +
            "update_time = #{updateTime}" +
            "</set> WHERE id = #{id}</script>")
    int updateSelective(UserDTO user);

    @Update("UPDATE ns_user SET password = #{password}, salt = #{salt}, update_time = #{updateTime} WHERE id = #{id}")
    int updatePassword(@Param("id") Long id, @Param("password") String password, @Param("salt") String salt, @Param("updateTime") LocalDateTime updateTime);

    @Update("UPDATE ns_user SET email = NULL, update_time = #{updateTime} WHERE id = #{id}")
    int clearEmail(@Param("id") Long id, @Param("updateTime") LocalDateTime updateTime);

    @Update("UPDATE ns_user SET phone = NULL, update_time = #{updateTime} WHERE id = #{id}")
    int clearPhone(@Param("id") Long id, @Param("updateTime") LocalDateTime updateTime);

    @Select("SELECT COUNT(*) FROM ns_user WHERE name = #{name}")
    long countByName(String name);

    @Select("SELECT COUNT(*) FROM ns_user WHERE phone = #{phone}")
    long countByPhone(String phone);

    @Select("SELECT COUNT(*) FROM ns_user WHERE email = #{email}")
    long countByEmail(String email);

    @Select("SELECT * FROM ns_user ORDER BY id")
    List<UserListDTO> selectAllList();
}
