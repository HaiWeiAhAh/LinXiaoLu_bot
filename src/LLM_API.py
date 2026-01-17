
from openai import OpenAI
from utils.config import ConfigManager



# LLM_API.py 修正
async def UseAPI(current_uesrmsg, global_cfg: ConfigManager, llm_role: str = None, history: list | None = None):
    """
    :内部方法
    :current_uesrmsg:当前用户发送的消息
    :history: 历史消息，类型为元组列表如（[("usermsg","aimsg")]）
    :return: str
    """
    try:
        # 初始化系统的角色
        message = []
        if llm_role:
            message.append({'role': 'system', 'content': llm_role})
        # 历史消息构建
        if history:  # 修复：先判断history是否存在，再遍历
            for user_msg, ai_msg in history:
                message.append({'role': 'user', 'content': user_msg})
                message.append({'role': 'assistant', 'content': ai_msg})
        # 添加当前用户消息
        message.append({'role': 'user', 'content': current_uesrmsg})

        # 创建连接
        client = OpenAI(
            api_key=global_cfg.get("openai", "api_key"),
            base_url=global_cfg.get("openai", "base_url"),
        )
        # 构建回复（修复：传参为message而非current_uesrmsg）
        response = client.chat.completions.create(
            model=global_cfg.get("openai", "model"),
            messages=message,  # 关键修正
            stream=True
        )
        # 拼接流式响应
        message_str = ""
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                message_str += chunk.choices[0].delta.content
        return message_str
    except Exception as e:
        raise  # 抛出异常让上层处理