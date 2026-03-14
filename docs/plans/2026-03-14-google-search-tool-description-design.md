# Google Search Tool 描述规范设计

## 背景

当前 `GoogleSearchTool` 的 description 和 parameters 定义不够清晰，无法让 LLM 免费理解工具的用途和参数含义。需要建立统一的规范，改进所有工具的描述方式。

## 目标
1. 改进 `GoogleSearchTool` 的 description 和 parameters
2. 改进 `graph.py` 的 `_build_action_space()` 生成更清晰的工具描述
3. 为未来新增工具提供参考模板

4. 更新 `web_content.py` 的 description 和 parameters（可选)

5. 更新相关测试

