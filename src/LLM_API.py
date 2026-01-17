
from openai import OpenAI
from utils.config import ConfigManager



async  def UseAPI(current_uesrmsg,global_cfg:ConfigManager,llm_role:str = None,history: list | None = None,):
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
            message = [
                {'role': 'system', 'content': llm_role},
            ]
        # 历史消息构建
        for user_msg, ai_msg in history:
            if history:
                message.append({'role': 'user', 'content': user_msg})
                message.append({'role': 'assistant', 'content': ai_msg})
        message.append({'role': 'user', 'content': current_uesrmsg})

        # 创建连接
        client = OpenAI(
            api_key=global_cfg.get("openai", "api_key"),
            base_url=global_cfg.get("openai", "base_url"),
        )
        # 构建回复
        response = client.chat.completions.create(
            model=global_cfg.get("openai","model"),
            messages=current_uesrmsg,
            stream=True
        )
        # 清空消息防止消息堆积
        message_str = ""
        # 接受消息
        for chunk in response:
            if not chunk.choices:
                continue
            if chunk.choices[0].delta.content:
                message_str += chunk.choices[0].delta.content
        return message_str
    except Exception as e:
        #logger.error(f"API调用失败{str(e)}", exc_info=True)
        raise