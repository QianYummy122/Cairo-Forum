package com.liang.bbs.auth.service.impl;

import com.alibaba.fastjson.JSON;
import com.github.pagehelper.PageInfo;
import com.liang.bbs.auth.persistence.mapper.UserMapper;
import com.liang.bbs.auth.utils.PasswordUtils;
import com.liang.manage.auth.facade.dto.user.UserDTO;
import com.liang.manage.auth.facade.dto.user.UserEmailDTO;
import com.liang.manage.auth.facade.dto.user.UserListDTO;
import com.liang.manage.auth.facade.dto.user.UserLoginDTO;
import com.liang.manage.auth.facade.dto.user.UserPasswordDTO;
import com.liang.manage.auth.facade.dto.user.UserSearchDTO;
import com.liang.manage.auth.facade.dto.user.UserStateDTO;
import com.liang.manage.auth.facade.dto.user.UserRoleOrgDTO;
import com.liang.manage.auth.facade.dto.user.UserTokenDTO;
import com.liang.manage.auth.facade.server.FileService;
import com.liang.manage.auth.facade.server.MailService;
import com.liang.manage.auth.facade.server.SmsService;
import com.liang.manage.auth.facade.server.UserService;
import com.liang.nansheng.common.auth.RoleSsoDTO;
import com.liang.nansheng.common.auth.UserSsoDTO;
import com.liang.nansheng.common.enums.GenderEnum;
import com.liang.nansheng.common.enums.ResponseCode;
import com.liang.nansheng.common.enums.RoleGradeEnum;
import com.liang.nansheng.common.utils.VerifyCodeUtils;
import com.liang.nansheng.common.web.exception.BusinessException;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.lang3.StringUtils;
import org.apache.dubbo.config.annotation.Service;
import org.springframework.beans.BeanUtils;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * 用户服务（登录/注册/SSO token/用户信息），替代作者 ns-manage 的 UserService
 *
 * @author bbs-auth
 */
@Slf4j
@Component
@Service
public class UserServiceImpl implements UserService {

    private static final String SSO_TOKEN_KEY = "ns:sso:token:";
    private static final String VERIFY_EMAIL_KEY = "ns:verify:email:";
    private static final String VERIFY_SMS_KEY = "ns:verify:sms:";
    private static final long SSO_TTL_SECONDS = 7L * 24 * 60 * 60;
    private static final long VERIFY_TTL_SECONDS = 5L * 60;

    @Autowired
    private UserMapper userMapper;

    @Autowired
    private StringRedisTemplate stringRedisTemplate;

    @Autowired
    private MailService mailService;

    @Autowired
    private SmsService smsService;

    @Autowired
    private FileService fileService;

    // ---------------------------------------------------------------------
    // 登录 / 注册 / Token
    // ---------------------------------------------------------------------

    @Override
    public UserTokenDTO login(UserLoginDTO userLoginDTO) {
        UserDTO user = userMapper.selectByName(userLoginDTO.getName());
        if (user == null) {
            throw BusinessException.build(ResponseCode.NOT_EXISTS, "用户不存在");
        }
        if (!PasswordUtils.matches(userLoginDTO.getPassword(), user.getSalt(), user.getPassword())) {
            throw BusinessException.build(ResponseCode.NOT_MATCH, "用户名或密码错误");
        }
        if (user.getState() != null && !user.getState()) {
            throw BusinessException.build(ResponseCode.DATA_ILLEGAL, "账号已被禁用");
        }
        return generateUserToken(user.getId(), user.getName());
    }

    @Override
    public UserTokenDTO register(UserDTO userDTO) {
        if (userMapper.countByName(userDTO.getName()) > 0) {
            throw BusinessException.build(ResponseCode.NAME_EXIST, "用户名已存在");
        }
        String salt = PasswordUtils.generateSalt();
        userDTO.setSalt(salt);
        userDTO.setPassword(PasswordUtils.encrypt(userDTO.getPassword(), salt));
        LocalDateTime now = LocalDateTime.now();
        userDTO.setCreateTime(now);
        userDTO.setUpdateTime(now);
        userDTO.setState(true);
        if (userDTO.getGender() == null) {
            userDTO.setGender(GenderEnum.BOY.getCode());
        }
        if (userMapper.insert(userDTO) <= 0) {
            throw BusinessException.build(ResponseCode.OPERATE_FAIL, "注册失败");
        }
        return generateUserToken(userDTO.getId(), userDTO.getName());
    }

    @Override
    public UserTokenDTO registerAuth(UserDTO userDTO) {
        UserDTO exist = userMapper.selectByAuth(userDTO.getAuthId(), userDTO.getAuthSource());
        if (exist != null) {
            return generateUserToken(exist.getId(), exist.getName());
        }
        if (userMapper.countByName(userDTO.getName()) > 0) {
            userDTO.setName(userDTO.getName() + "_" + UUID.randomUUID().toString().substring(0, 4));
        }
        String salt = PasswordUtils.generateSalt();
        userDTO.setSalt(salt);
        userDTO.setPassword(PasswordUtils.encrypt(UUID.randomUUID().toString(), salt));
        LocalDateTime now = LocalDateTime.now();
        userDTO.setCreateTime(now);
        userDTO.setUpdateTime(now);
        userDTO.setState(true);
        if (userMapper.insert(userDTO) <= 0) {
            throw BusinessException.build(ResponseCode.OPERATE_FAIL, "三方登录注册失败");
        }
        return generateUserToken(userDTO.getId(), userDTO.getName());
    }

    @Override
    public Boolean isExpired(String token) {
        return !Boolean.TRUE.equals(stringRedisTemplate.hasKey(SSO_TOKEN_KEY + token));
    }

    @Override
    public UserTokenDTO generateUserToken(Long userid, String username) {
        UserDTO user = userMapper.selectById(userid);
        if (user == null) {
            throw BusinessException.build(ResponseCode.NOT_EXISTS, "用户不存在");
        }
        String token = UUID.randomUUID().toString().replace("-", "");
        UserSsoDTO sso = buildUserSso(user);
        stringRedisTemplate.opsForValue().set(SSO_TOKEN_KEY + token, JSON.toJSONString(sso), SSO_TTL_SECONDS, TimeUnit.SECONDS);
        UserTokenDTO tokenDTO = new UserTokenDTO();
        tokenDTO.setUserId(userid);
        tokenDTO.setUsername(username);
        tokenDTO.setToken(token);
        return tokenDTO;
    }

    @Override
    public UserSsoDTO getUserSsoDTOByToken(String token) {
        String json = stringRedisTemplate.opsForValue().get(SSO_TOKEN_KEY + token);
        if (StringUtils.isBlank(json)) {
            return null;
        }
        return JSON.parseObject(json, UserSsoDTO.class);
    }

    @Override
    public Boolean verifyToken(String token) {
        return stringRedisTemplate.hasKey(SSO_TOKEN_KEY + token);
    }

    @Override
    public Long getClaim(String token) {
        UserSsoDTO sso = getUserSsoDTOByToken(token);
        return sso == null ? null : sso.getUserId();
    }

    @Override
    public String innerLoginUrl(String referer) {
        return referer;
    }

    @Override
    public void logout(String token) {
        stringRedisTemplate.delete(SSO_TOKEN_KEY + token);
    }

    // ---------------------------------------------------------------------
    // 用户查询
    // ---------------------------------------------------------------------

    @Override
    public PageInfo<UserListDTO> getList(UserSearchDTO userSearchDTO) {
        // 管理端用户列表，论坛前端未使用，占位返回空
        return new PageInfo<>(new ArrayList<>());
    }

    @Override
    public List<UserListDTO> getAllList() {
        return userMapper.selectAllList();
    }

    @Override
    public Map<Integer, String> getGender() {
        Map<Integer, String> map = new HashMap<>();
        for (GenderEnum gender : GenderEnum.values()) {
            map.put(gender.getCode(), gender.getName());
        }
        return map;
    }

    @Override
    public UserDTO getById(Long userid) {
        return userMapper.selectById(userid);
    }

    @Override
    public List<UserDTO> getByIds(List<Long> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            return Collections.emptyList();
        }
        return userMapper.selectByIds(userIds);
    }

    @Override
    public List<UserDTO> getListByRoleId(Integer roleId) {
        return Collections.emptyList();
    }

    @Override
    public List<UserDTO> notUserOfThisRole(List<Integer> roleIds) {
        return Collections.emptyList();
    }

    @Override
    public UserListDTO getUserListById(Long userid) {
        UserDTO user = userMapper.selectById(userid);
        if (user == null) {
            return null;
        }
        UserListDTO dto = new UserListDTO();
        BeanUtils.copyProperties(user, dto);
        return dto;
    }

    @Override
    public List<UserListDTO> getNewUser() {
        return Collections.emptyList();
    }

    @Override
    public UserDTO getByPhone(String phone) {
        return userMapper.selectByPhone(phone);
    }

    @Override
    public UserDTO getByEmail(String email) {
        return userMapper.selectByEmail(email);
    }

    // ---------------------------------------------------------------------
    // 用户更新
    // ---------------------------------------------------------------------

    @Override
    public Boolean updateUserRolesOrg(UserRoleOrgDTO userRoleOrgDTO, UserSsoDTO currentUser) {
        // 管理端功能，论坛前端未使用
        return true;
    }

    @Override
    public Boolean changeStatus(UserStateDTO userStateDTO) {
        // 管理端功能，论坛前端未使用
        return true;
    }

    @Override
    public Boolean uploadUserPicture(byte[] bytes, String sourceFileName, UserSsoDTO currentUser) {
        String url = fileService.fileCutUpload(bytes, sourceFileName, "headPortrait");
        UserDTO update = new UserDTO();
        update.setId(currentUser.getUserId());
        update.setPicture(url);
        update.setUpdateTime(LocalDateTime.now());
        userMapper.updateSelective(update);
        return true;
    }

    @Override
    public Boolean updateUserBasicInfo(UserDTO userDTO, UserSsoDTO currentUser) {
        UserDTO update = new UserDTO();
        update.setId(currentUser.getUserId());
        // 用户名（昵称）允许修改，需保证唯一（排除自身）
        if (StringUtils.isNotBlank(userDTO.getName())) {
            UserDTO exist = userMapper.selectByName(userDTO.getName());
            if (exist != null && !exist.getId().equals(currentUser.getUserId())) {
                throw BusinessException.build(ResponseCode.NAME_EXIST, "用户名已存在");
            }
            update.setName(userDTO.getName());
        }
        update.setGender(userDTO.getGender());
        update.setBirthday(userDTO.getBirthday());
        update.setIntro(userDTO.getIntro());
        update.setPosition(userDTO.getPosition());
        update.setCompany(userDTO.getCompany());
        update.setHomePage(userDTO.getHomePage());
        update.setUpdateTime(LocalDateTime.now());
        return userMapper.updateSelective(update) > 0;
    }

    @Override
    public Boolean updatePassword(UserPasswordDTO passwordDTO, UserSsoDTO currentUser) {
        UserDTO user = userMapper.selectById(currentUser.getUserId());
        if (user == null || !PasswordUtils.matches(passwordDTO.getOldPassword(), user.getSalt(), user.getPassword())) {
            throw BusinessException.build(ResponseCode.NOT_MATCH, "原密码错误");
        }
        String salt = PasswordUtils.generateSalt();
        return userMapper.updatePassword(user.getId(), PasswordUtils.encrypt(passwordDTO.getNewPassword(), salt), salt, LocalDateTime.now()) > 0;
    }

    @Override
    public Map<String, Object> uploadCommonPicture(byte[] bytes, String sourceFileName, UserSsoDTO currentUser) {
        String url = fileService.fileCutUpload(bytes, sourceFileName, "otherPicture");
        Map<String, Object> result = new HashMap<>();
        result.put("url", url);
        return result;
    }

    @Override
    public void updateAllUserBaseRole() {
        // 无基础角色概念，占位
    }

    @Override
    public void updateAllUserDefaultHead() {
        // 占位
    }

    // ---------------------------------------------------------------------
    // 邮箱 / 手机 绑定与验证码
    // ---------------------------------------------------------------------

    @Override
    public Boolean sendEmailVerifyCode(String email, UserSsoDTO currentUser) {
        String code = VerifyCodeUtils.generateVerifyCode(6);
        stringRedisTemplate.opsForValue().set(VERIFY_EMAIL_KEY + email, code, VERIFY_TTL_SECONDS, TimeUnit.SECONDS);
        mailService.sendSimpleMail(email, "开罗论坛验证码", "您的验证码是：" + code + "，5分钟内有效。");
        return true;
    }

    @Override
    public Boolean sendSmsVerifyCode(String phone, UserSsoDTO currentUser) {
        String code = VerifyCodeUtils.generateVerifyCode(6);
        stringRedisTemplate.opsForValue().set(VERIFY_SMS_KEY + phone, code, VERIFY_TTL_SECONDS, TimeUnit.SECONDS);
        smsService.sendSms(phone, code);
        return true;
    }

    @Override
    public Boolean bindEmail(UserEmailDTO userEmailDTO, UserSsoDTO currentUser) {
        checkVerifyCode(VERIFY_EMAIL_KEY + userEmailDTO.getEmail(), userEmailDTO.getCode());
        if (isEmailExist(userEmailDTO.getEmail())) {
            throw BusinessException.build(ResponseCode.NAME_EXIST, "邮箱已被绑定");
        }
        UserDTO update = new UserDTO();
        update.setId(currentUser.getUserId());
        update.setEmail(userEmailDTO.getEmail());
        update.setUpdateTime(LocalDateTime.now());
        return userMapper.updateSelective(update) > 0;
    }

    @Override
    public Boolean bindPhone(UserEmailDTO userEmailDTO, UserSsoDTO currentUser) {
        checkVerifyCode(VERIFY_SMS_KEY + userEmailDTO.getPhone(), userEmailDTO.getCode());
        if (isPhoneExist(userEmailDTO.getPhone())) {
            throw BusinessException.build(ResponseCode.NAME_EXIST, "手机号已被绑定");
        }
        UserDTO update = new UserDTO();
        update.setId(currentUser.getUserId());
        update.setPhone(userEmailDTO.getPhone());
        update.setUpdateTime(LocalDateTime.now());
        return userMapper.updateSelective(update) > 0;
    }

    @Override
    public Boolean untieEmail(UserSsoDTO currentUser) {
        return userMapper.clearEmail(currentUser.getUserId(), LocalDateTime.now()) > 0;
    }

    @Override
    public Boolean untiePhone(UserSsoDTO currentUser) {
        return userMapper.clearPhone(currentUser.getUserId(), LocalDateTime.now()) > 0;
    }

    @Override
    public Boolean isValidEmail(String email) {
        return userMapper.countByEmail(email) == 0;
    }

    @Override
    public Boolean isValidPhone(String phone) {
        return userMapper.countByPhone(phone) == 0;
    }

    @Override
    public Boolean isValidUser(String userName, UserSsoDTO currentUser) {
        return userMapper.countByName(userName) == 0;
    }

    @Override
    public Boolean isPhoneExist(String phone) {
        return userMapper.countByPhone(phone) > 0;
    }

    @Override
    public Boolean isEmailExist(String email) {
        return userMapper.countByEmail(email) > 0;
    }

    @Override
    public Boolean phoneResetPassword(UserEmailDTO userEmailDTO) {
        checkVerifyCode(VERIFY_SMS_KEY + userEmailDTO.getPhone(), userEmailDTO.getCode());
        UserDTO user = userMapper.selectByPhone(userEmailDTO.getPhone());
        if (user == null) {
            throw BusinessException.build(ResponseCode.NOT_EXISTS, "用户不存在");
        }
        String salt = PasswordUtils.generateSalt();
        return userMapper.updatePassword(user.getId(), PasswordUtils.encrypt(userEmailDTO.getNewPassword(), salt), salt, LocalDateTime.now()) > 0;
    }

    @Override
    public Boolean emailResetPassword(UserEmailDTO userEmailDTO) {
        checkVerifyCode(VERIFY_EMAIL_KEY + userEmailDTO.getEmail(), userEmailDTO.getCode());
        UserDTO user = userMapper.selectByEmail(userEmailDTO.getEmail());
        if (user == null) {
            throw BusinessException.build(ResponseCode.NOT_EXISTS, "用户不存在");
        }
        String salt = PasswordUtils.generateSalt();
        return userMapper.updatePassword(user.getId(), PasswordUtils.encrypt(userEmailDTO.getNewPassword(), salt), salt, LocalDateTime.now()) > 0;
    }

    // ---------------------------------------------------------------------
    // 闲聊（未使用，占位）
    // ---------------------------------------------------------------------

    @Override
    public void insertChatUser(String userName) {
        log.info("[CHAT] insertChatUser mock: {}", userName);
    }

    @Override
    public void insertGroup(String id) {
        log.info("[CHAT] insertGroup mock: {}", id);
    }

    @Override
    public Boolean checkIdempotent(String url, Integer timeout, TimeUnit timeUnit) {
        if (timeout == null || timeUnit == null) {
            timeout = 5;
            timeUnit = TimeUnit.SECONDS;
        }
        Boolean set = stringRedisTemplate.opsForValue().setIfAbsent("ns:idem:" + url, "1", timeout, timeUnit);
        return Boolean.TRUE.equals(set);
    }

    // ---------------------------------------------------------------------
    // 私有方法
    // ---------------------------------------------------------------------

    private void checkVerifyCode(String key, String code) {
        String realCode = stringRedisTemplate.opsForValue().get(key);
        if (StringUtils.isBlank(realCode) || !realCode.equals(code)) {
            throw BusinessException.build(ResponseCode.DATA_EXPIRED, "验证码错误或已过期");
        }
    }

    private UserSsoDTO buildUserSso(UserDTO user) {
        UserSsoDTO sso = new UserSsoDTO();
        sso.setUserId(user.getId());
        sso.setUserName(user.getName());
        sso.setGender(user.getGender());
        sso.setBirthday(user.getBirthday());
        sso.setPhone(user.getPhone());
        sso.setEmail(user.getEmail());
        sso.setPicture(user.getPicture());
        sso.setIntro(user.getIntro());
        sso.setOrgId(user.getOrgId());

        List<RoleSsoDTO> roles = new ArrayList<>();
        if (Boolean.TRUE.equals(userMapper.selectIsAdmin(user.getId()))) {
            RoleSsoDTO admin = new RoleSsoDTO();
            admin.setId(1);
            admin.setCode("ns-super-admin");
            admin.setName("超级管理员");
            admin.setGrade(RoleGradeEnum.NS_SUPER_ADMIN_ROLE.name());
            roles.add(admin);
        }
        sso.setRoles(roles);
        return sso;
    }
}
