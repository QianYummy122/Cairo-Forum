"""论坛内容数据源：把小罗Bot 与开罗论坛（springboot 后台）对接起来。

设计说明
--------
小罗Bot 要回答"论坛里有没有相关内容"，就必须先把论坛的内容变成可检索的知识库。
论坛的数据在 springboot 微服务里（bbs-article / bbs-user 域，MySQL + MongoDB），
因此本模块提供三种数据源，按优先级自动降级：

1. ``RestForumSource``   —— 通过 **springboot 的 REST 网关 bbs-rest**（``/api/bbs/...``）
    拉取文章、评论、标签、资源导航。这是**推荐方式**，也是"MultimodalRAG 对接
    springboot 后台"的那条链路的正向部分：
    不直连数据库、不复制业务 SQL，网关改了字段这里跟着字段名读，职责边界干净。

2. ``MysqlForumSource``  —— 网关或 Dubbo/ZooKeeper 没起来时的兜底，直连 ``open_bbs``
    只读查询。仅用于离线构建知识库，不参与线上问答。

3. ``LocalSnapshotSource`` —— 完全离线时读取 ``forum_snapshot/`` 下的 md/txt/json。

三种数据源产出的都是统一的 :class:`ForumDocument`，后续入库流程完全一致。
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Dict, Iterable, Iterator, List, Optional

from utils.config import CONFIG
from utils.log_utils import log

# ---------------------------------------------------------------------------
# 统一的数据结构
# ---------------------------------------------------------------------------


@dataclass
class ForumDocument:
    """论坛里的一条可入库内容（一篇帖子 / 一条评论 / 一个资源 / 一个标签）。"""

    # 稳定唯一的业务主键，用于去重与增量更新（例如 "article:43"）
    doc_id: str
    # 内容类型：article / comment / resource / label / snapshot / pdf
    source_type: str
    title: str
    content: str
    # 论坛内的可访问路径（相对站点根），回答里会作为引用链接给用户
    source_url: str = ""
    author: str = ""
    created_at: str = ""
    # 正文中的图片（http(s) URL 或本地路径），用于多模态向量化
    images: List[str] = field(default_factory=list)
    labels: List[str] = field(default_factory=list)

    @property
    def display_source(self) -> str:
        """展示给人看的来源名，例如 "文章《Hello》"。"""
        prefix = {
            "article": "文章",
            "comment": "评论",
            "resource": "资源",
            "label": "标签",
            "snapshot": "本地文档",
            "pdf": "文档",
        }.get(self.source_type, "内容")
        return f"{prefix}《{self.title}》" if self.title else prefix


# ---------------------------------------------------------------------------
# 图片链接提取（Markdown / HTML / 裸链接）
# ---------------------------------------------------------------------------

_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")
_HTML_IMAGE_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)
_BARE_IMAGE_RE = re.compile(
    r"https?://[^\s\"'<>)]+?\.(?:png|jpe?g|gif|webp|bmp|svg)(?:\?[^\s\"'<>)]*)?",
    re.IGNORECASE,
)


def extract_image_urls(text: str, limit: int = None) -> List[str]:
    """从 Markdown / HTML 正文中抽取图片地址（去重、保序、可限量）。"""
    if not text:
        return []
    found: List[str] = []
    for pattern in (_MD_IMAGE_RE, _HTML_IMAGE_RE, _BARE_IMAGE_RE):
        found.extend(pattern.findall(text))
    # data URI 交给多模态接口直接吃，其它一律走 URL
    seen, result = set(), []
    for url in found:
        url = url.strip()
        if not url or url in seen:
            continue
        seen.add(url)
        result.append(url)
    if limit is not None:
        result = result[:limit]
    return result


def strip_images(text: str) -> str:
    """去掉正文里的图片语法，只保留文本（图片会单独作为多模态文档入库）。"""
    if not text:
        return ""
    text = _MD_IMAGE_RE.sub("", text)
    text = _HTML_IMAGE_RE.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _clean_text(raw: Optional[str]) -> str:
    """去掉 HTML 标签、压缩空白，得到干净的纯文本。"""
    if not raw:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", "", raw, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", raw, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r"[ \t\u00a0]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 数据源基类
# ---------------------------------------------------------------------------


class ForumSource:
    """论坛数据源抽象。"""

    name = "base"

    def available(self) -> bool:
        """数据源当前是否可用（用于自动降级）。"""
        return False

    def fetch(self) -> Iterator[ForumDocument]:
        raise NotImplementedError

    # -- 供日志/接口展示 ----------------------------------------------------
    def describe(self) -> Dict[str, object]:
        return {"name": self.name, "available": self.available()}


# ---------------------------------------------------------------------------
# 方式一：springboot REST 网关（推荐）
# ---------------------------------------------------------------------------


class RestForumSource(ForumSource):
    """通过 bbs-rest 网关拉取论坛内容。

    网关地址形如 ``http://127.0.0.1:7010/api``，接口是 ``@NoNeedLogin`` 的公开读接口，
    返回统一信封 ``{"code": 0, "desc": "成功", "data": ...}``。
    """

    name = "springboot-rest"

    def __init__(self) -> None:
        self.base_url = str(CONFIG.get("forum.base_url", "http://127.0.0.1:7010/api")).rstrip("/")
        self.timeout = CONFIG.get("forum.rest_timeout", 30)
        self.page_size = CONFIG.get("forum.page_size", 50)
        self.max_pages = CONFIG.get("forum.max_pages", 40)
        self.ep = CONFIG.section("forum.endpoints")
        self.max_images = CONFIG.get("forum.max_images_per_article", 3)
        # 允许在配置里直接禁用（例如纯离线环境）
        self._enabled = bool(CONFIG.get("forum.enabled", True))

    # -- 底层请求 -----------------------------------------------------------
    def _get(self, path: str, params: Dict = None):
        """调用网关接口并解包统一响应信封，失败返回 None。"""
        import requests

        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, params=params or {}, timeout=self.timeout)
            resp.raise_for_status()
            body = resp.json()
        except Exception as e:  # 网络异常 / 非 JSON / 4xx5xx
            log.warning(f"[forum-rest] 请求 {url} 失败：{e}")
            return None

        code = body.get("code")
        if code != 0:
            # code=302 表示未登录（本场景下不应出现，因为接口都是 @NoNeedLogin）
            log.warning(f"[forum-rest] {url} 返回 code={code}, desc={body.get('desc')}")
            return None
        return body.get("data")

    def available(self) -> bool:
        if not self._enabled:
            return False
        # 用一个最轻的读接口探活：文章列表第 1 页取 1 条
        data = self._get(self.ep.get("article_list", "/bbs/article/getList"),
                         {"currentPage": 1, "pageSize": 1})
        return data is not None

    # -- 各类内容 -----------------------------------------------------------
    def _iter_article_summaries(self) -> Iterator[Dict]:
        """翻页拉取文章列表。"""
        for page in range(1, int(self.max_pages) + 1):
            data = self._get(self.ep.get("article_list", "/bbs/article/getList"),
                             {"currentPage": page, "pageSize": self.page_size})
            if not data:
                break
            rows = data.get("list") or []
            if not rows:
                break
            for row in rows:
                yield row
            if not data.get("hasNextPage"):
                break

    def _article_detail(self, article_id: int) -> Optional[Dict]:
        return self._get(self.ep.get("article_detail", "/bbs/article/getById"), {"id": article_id})

    def _comments(self, article_id: int) -> List[Dict]:
        data = self._get(self.ep.get("comment_list", "/bbs/comment/getCommentByArticleId"),
                         {"articleId": article_id})
        return data or []

    @staticmethod
    def _flatten_comments(comments: List[Dict]) -> Iterator[Dict]:
        """评论是树形结构（child 嵌套），这里拍平。"""
        stack = list(comments or [])
        while stack:
            node = stack.pop(0)
            yield node
            stack.extend(node.get("child") or [])

    def fetch(self) -> Iterator[ForumDocument]:
        # ---------- 文章 ----------
        article_ids: List[int] = []
        for summary in self._iter_article_summaries():
            article_id = summary.get("id")
            if article_id is None:
                continue
            article_ids.append(article_id)
            # 详情接口才有 markdown 正文，拿不到就退回列表里的字段
            detail = self._article_detail(article_id) or summary
            yield self._to_article_doc(detail)

        # ---------- 评论（按文章逐篇拉取）----------
        for article_id in article_ids:
            for comment in self._flatten_comments(self._comments(article_id)):
                doc = self._to_comment_doc(comment, article_id)
                if doc:
                    yield doc

        # ---------- 资源导航 ----------
        yield from self._fetch_paged(self.ep.get("resource_list", "/bbs/resource/getList"),
                                     self._to_resource_doc, "resource")

        # ---------- 标签 ----------
        yield from self._fetch_paged(self.ep.get("label_list", "/bbs/label/getList"),
                                     self._to_label_doc, "label")

    def _fetch_paged(self, path: str, mapper, kind: str) -> Iterator[ForumDocument]:
        for page in range(1, int(self.max_pages) + 1):
            data = self._get(path, {"currentPage": page, "pageSize": self.page_size})
            if not data:
                break
            rows = data.get("list") if isinstance(data, dict) else data
            if not rows:
                break
            for row in rows:
                doc = mapper(row)
                if doc:
                    yield doc
            if not (isinstance(data, dict) and data.get("hasNextPage")):
                break

    # -- 映射函数 -----------------------------------------------------------
    def _to_article_doc(self, a: Dict) -> ForumDocument:
        article_id = a.get("id")
        raw_body = a.get("markdown") or a.get("content") or ""
        images = extract_image_urls(raw_body, self.max_images)
        picture = a.get("picture")
        if picture and picture not in images:
            images.insert(0, picture)
        labels = [l.get("labelName") for l in (a.get("labelDTOS") or []) if l.get("labelName")]
        body = _clean_text(strip_images(raw_body))
        return ForumDocument(
            doc_id=f"article:{article_id}",
            source_type="article",
            title=a.get("title") or f"文章 {article_id}",
            content=body,
            source_url=f"/detail/{article_id}",
            author=a.get("createUserName") or "",
            created_at=str(a.get("createTime") or ""),
            images=images[: self.max_images + 1],
            labels=labels,
        )

    def _to_comment_doc(self, c: Dict, article_id: int) -> Optional[ForumDocument]:
        content = _clean_text(c.get("content"))
        if not content:
            return None
        return ForumDocument(
            doc_id=f"comment:{c.get('id')}",
            source_type="comment",
            title=f"文章 {article_id} 的评论",
            content=content,
            source_url=f"/detail/{article_id}",
            author=c.get("commentUserName") or "",
            created_at=str(c.get("createTime") or ""),
        )

    def _to_resource_doc(self, r: Dict) -> Optional[ForumDocument]:
        name = r.get("resourceName")
        if not name:
            return None
        text = f"资源名称：{name}\n资源类别：{r.get('category') or '未分类'}\n资源描述：{r.get('desc') or ''}\n资源链接：{r.get('link') or ''}"
        return ForumDocument(
            doc_id=f"resource:{r.get('id')}",
            source_type="resource",
            title=name,
            content=text,
            source_url=r.get("link") or "/resource",
            created_at=str(r.get("createTime") or ""),
            labels=[r.get("category")] if r.get("category") else [],
        )

    def _to_label_doc(self, l: Dict) -> Optional[ForumDocument]:
        name = l.get("labelName")
        if not name:
            return None
        return ForumDocument(
            doc_id=f"label:{l.get('id')}",
            source_type="label",
            title=name,
            content=f"论坛标签：{name}，已被 {l.get('articleUseCount') or 0} 篇文章使用。",
            source_url=f"/label/{l.get('id')}",
        )


# ---------------------------------------------------------------------------
# 方式二：直连 MySQL（网关不可用时的兜底）
# ---------------------------------------------------------------------------


class MysqlForumSource(ForumSource):
    """直连 ``open_bbs`` 只读导出。仅在 REST 网关不可用时使用。"""

    name = "mysql"

    def __init__(self) -> None:
        cfg = CONFIG.section("forum.mysql")
        self.enabled = bool(cfg.get("enabled", True))
        self.host = cfg.get("host", "127.0.0.1")
        self.port = int(cfg.get("port", 3306))
        self.user = cfg.get("user", "root")
        self.password = str(cfg.get("password", ""))
        self.database = cfg.get("database", "open_bbs")
        self.charset = cfg.get("charset", "utf8mb4")
        self.max_images = CONFIG.get("forum.max_images_per_article", 3)

    def _connect(self):
        import pymysql

        return pymysql.connect(
            host=self.host, port=self.port, user=self.user, password=self.password,
            database=self.database, charset=self.charset, cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5, read_timeout=30,
        )

    def available(self) -> bool:
        if not self.enabled:
            return False
        try:
            conn = self._connect()
            conn.close()
            return True
        except Exception as e:
            log.info(f"[forum-mysql] 不可用：{e}")
            return False

    def _query(self, conn, sql: str, args: tuple = ()) -> List[Dict]:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return list(cur.fetchall())

    def fetch(self) -> Iterator[ForumDocument]:
        conn = self._connect()
        try:
            # ---------- 文章 + 标签 ----------
            articles = self._query(
                conn,
                "SELECT id, title, content, state, pv, create_user, create_time "
                "FROM fs_article WHERE (is_deleted = 0 OR is_deleted IS NULL) AND state = 1 "
                "ORDER BY id ASC",
            )
            label_map: Dict[int, List[str]] = {}
            for row in self._query(
                conn,
                "SELECT al.article_id AS article_id, l.label_name AS label_name "
                "FROM fs_article_label al JOIN fs_label l ON l.id = al.label_id",
            ):
                label_map.setdefault(row["article_id"], []).append(row["label_name"])

            article_ids: List[int] = []
            for a in articles:
                article_ids.append(a["id"])
                raw = a.get("content") or ""
                images = extract_image_urls(raw, self.max_images)
                yield ForumDocument(
                    doc_id=f"article:{a['id']}",
                    source_type="article",
                    title=a.get("title") or f"文章 {a['id']}",
                    content=_clean_text(strip_images(raw)),
                    source_url=f"/detail/{a['id']}",
                    created_at=str(a.get("create_time") or ""),
                    images=images,
                    labels=label_map.get(a["id"], []),
                )

            # ---------- 评论 ----------
            if article_ids:
                placeholders = ",".join(["%s"] * len(article_ids))
                comments = self._query(
                    conn,
                    f"SELECT id, content, article_id, comment_user, create_time FROM fs_comment "
                    f"WHERE article_id IN ({placeholders}) AND (is_deleted = 0 OR is_deleted IS NULL)",
                    tuple(article_ids),
                )
                for c in comments:
                    content = _clean_text(c.get("content"))
                    if not content:
                        continue
                    yield ForumDocument(
                        doc_id=f"comment:{c['id']}",
                        source_type="comment",
                        title=f"文章 {c['article_id']} 的评论",
                        content=content,
                        source_url=f"/detail/{c['article_id']}",
                        created_at=str(c.get("create_time") or ""),
                    )

            # ---------- 资源导航 ----------
            for r in self._query(
                conn,
                "SELECT id, resource_name, category, `desc`, link, create_time FROM fs_resource_navigate "
                "WHERE is_deleted = 0 OR is_deleted IS NULL",
            ):
                if not r.get("resource_name"):
                    continue
                yield ForumDocument(
                    doc_id=f"resource:{r['id']}",
                    source_type="resource",
                    title=r["resource_name"],
                    content=(f"资源名称：{r['resource_name']}\n资源类别：{r.get('category') or '未分类'}\n"
                             f"资源描述：{r.get('desc') or ''}\n资源链接：{r.get('link') or ''}"),
                    source_url=r.get("link") or "/resource",
                    created_at=str(r.get("create_time") or ""),
                    labels=[r["category"]] if r.get("category") else [],
                )

            # ---------- 标签 ----------
            # article_use_count 在库里不是字段，而是 fs_article_label 的统计值，这里现算
            for l in self._query(
                conn,
                "SELECT l.id AS id, l.label_name AS label_name, "
                "       (SELECT COUNT(*) FROM fs_article_label al WHERE al.label_id = l.id "
                "        AND (al.is_deleted = 0 OR al.is_deleted IS NULL)) AS article_use_count "
                "FROM fs_label l WHERE l.is_deleted = 0 OR l.is_deleted IS NULL",
            ):
                if not l.get("label_name"):
                    continue
                yield ForumDocument(
                    doc_id=f"label:{l['id']}",
                    source_type="label",
                    title=l["label_name"],
                    content=f"论坛标签：{l['label_name']}，已被 {l.get('article_use_count') or 0} 篇文章使用。",
                    source_url=f"/label/{l['id']}",
                )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 方式三：本地快照（离线）
# ---------------------------------------------------------------------------


class LocalSnapshotSource(ForumSource):
    """读取 ``forum_snapshot/`` 下的 .md / .txt / .json，用于离线演示与测试。"""

    name = "local-snapshot"

    def __init__(self) -> None:
        self.dir = CONFIG.path("forum.local_dir")
        self.max_images = CONFIG.get("forum.max_images_per_article", 3)

    def available(self) -> bool:
        return self.dir.is_dir() and any(
            f.suffix.lower() in {".md", ".txt", ".json"} for f in self.dir.rglob("*") if f.is_file()
        )

    def fetch(self) -> Iterator[ForumDocument]:
        if not self.dir.is_dir():
            return
        for path in sorted(self.dir.rglob("*")):
            if not path.is_file():
                continue
            suffix = path.suffix.lower()
            if suffix not in {".md", ".txt", ".json"}:
                continue
            try:
                raw = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                log.warning(f"[forum-snapshot] 读取 {path} 失败：{e}")
                continue
            if not raw.strip():
                continue
            rel = path.relative_to(self.dir).as_posix()
            if suffix == ".json":
                # JSON：支持 {"title":..,"content":..,"url":..} 或 [ {...}, {...} ]
                yield from self._from_json(raw, rel)
            else:
                yield ForumDocument(
                    doc_id=f"snapshot:{rel}",
                    source_type="snapshot",
                    title=path.stem,
                    content=strip_images(raw),
                    source_url="",
                    images=extract_image_urls(raw, self.max_images),
                )

    def _from_json(self, raw: str, rel: str) -> Iterator[ForumDocument]:
        try:
            data = json.loads(raw)
        except Exception as e:
            log.warning(f"[forum-snapshot] {rel} 不是合法 JSON：{e}")
            return
        items = data if isinstance(data, list) else [data]
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            content = str(item.get("content") or item.get("text") or "")
            if not content:
                continue
            yield ForumDocument(
                doc_id=f"snapshot:{rel}#{item.get('id', idx)}",
                source_type="snapshot",
                title=str(item.get("title") or f"{rel}#{idx}"),
                content=strip_images(content),
                source_url=str(item.get("url") or ""),
                author=str(item.get("author") or ""),
                images=extract_image_urls(content, self.max_images),
                labels=list(item.get("labels") or []),
            )


# ---------------------------------------------------------------------------
# 工厂：按优先级挑选可用数据源
# ---------------------------------------------------------------------------


def build_sources(prefer: str = None) -> List[ForumSource]:
    """构造数据源列表。

    :param prefer: 指定优先使用的数据源名字（``springboot-rest`` / ``mysql`` /
        ``local-snapshot``）。为空时按 REST → MySQL → 本地快照 的优先级自动探测。
    """
    candidates: List[ForumSource] = [RestForumSource(), MysqlForumSource(), LocalSnapshotSource()]
    if prefer:
        ordered = [s for s in candidates if s.name == prefer]
        ordered += [s for s in candidates if s.name != prefer]
        return ordered
    return candidates


def pick_source(prefer: str = None) -> Optional[ForumSource]:
    """返回第一个可用的数据源；都不行则返回 None。"""
    for source in build_sources(prefer):
        if source.available():
            log.info(f"[forum] 使用数据源：{source.name}")
            return source
        log.info(f"[forum] 数据源 {source.name} 不可用，尝试下一个")
    return None


def source_status() -> List[Dict[str, object]]:
    """给 /kb/status 接口用的数据源健康状态。"""
    return [s.describe() for s in build_sources()]


__all__ = [
    "ForumDocument",
    "ForumSource",
    "RestForumSource",
    "MysqlForumSource",
    "LocalSnapshotSource",
    "build_sources",
    "pick_source",
    "source_status",
    "extract_image_urls",
    "strip_images",
]
