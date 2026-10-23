"""图上的 8 个节点，一个节点一个文件。

=================  ===============================  ==================================
图节点名            模块                             职责
=================  ===============================  ==================================
``prepare``         :mod:`agent.nodes.prepare`       每轮开头清空单轮状态
``supervisor``      :mod:`agent.nodes.supervisor`    规划：产出执行计划（唯一调模型）
``vision``          :mod:`agent.nodes.vision`        多模态理解：图片 → 可检索信息
``forum``           :mod:`agent.nodes.forum`         论坛检索：多模态 RAG + 可用性判定
``web``             :mod:`agent.nodes.web`           联网搜索：可开关的外部信息通道
``compose``         :mod:`agent.nodes.compose`       答案合成：流式产出带引用的回答
``evaluate``        :mod:`agent.nodes.evaluate`      质量评估：规则 + 模型双层把关
``rewrite``         :mod:`agent.nodes.rewrite`       补救准备：把要重做的步骤置为待执行
=================  ===============================  ==================================

**本文件故意不做 re-export。** 因为 ``forum`` 节点在导入时就会拉起 Milvus 检索器，
一旦 ``agent.nodes.__init__`` 把所有节点都 import 进来，那么"只想用一下
``rewrite_node``"的测试/脚本也会被迫连接向量库。所以装配处
（:mod:`agent.graph`）逐个显式导入，谁需要谁付代价。

不属于节点的东西不在这里：

- 条件边函数 + 预算判定（``route_next`` / ``route_after_agent`` /
  ``_web_available`` / ``_rewrite_available``）→ :mod:`agent.routing`；
- 图的装配 → :mod:`agent.graph`；
- 共享状态、事件协议、提示词、大模型调用 → 上一层 ``agent/`` 里。
"""
