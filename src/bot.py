# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import uuid
import random

from src.JM import search_comic, download_comics
from src.LLM_API import UseAPI,build_llm_vision_content
from src.napcat_msg import Group_Msg, choice_send_tpye


class MessageStreamObject:
    """
    :用于napcat的聊天流对象
    :argument 用于保存聊天记录和管理消息
    :example 以消息列表的形式表达
    ["2026-1-1 22:11:10 '小吕':‘什么贵，你知道吗’","2026-1-1 22:12:10 '小鹿':‘不知道’","2026-1-1 22:14:10 '小吕':‘太逊了’"]
    """


    GROUP = "group"
    ROLE_OWNER = {"owner":"群主"}
    ROLE_ADMIN = {"admin":"管理员"}
    ROLE_MEMBER = {"member":"群成员"}
    GROUP_ROLE =[ROLE_OWNER, ROLE_ADMIN, ROLE_MEMBER]
    SENDER_INFO =[]
    STREAM_TYPE = [GROUP]


    def __init__(self,group_id:int =None,stream_type:str=None):
        self.crate_time = time.time()
        self.stream_id = uuid.uuid4()
        self.stream_name: str = ""
        self.stream_msg: list = []  # 这里放置受到的群聊消息
        self.stream_type = stream_type
        self.stream_group_id = group_id
        self.have_new_message = False

    async def add_new_message(self,new_message:str,self_add:bool=False):
        self.stream_msg.append(new_message)
        if not self_add:
            self.have_new_message = True
    async def get_new_message(self,max_msg_count:int = 20) -> str:
        if not isinstance(max_msg_count, int) or max_msg_count <= 0:
            max_msg_count = 15
        if not self.have_new_message:
            return ""
        if not self.stream_msg:
            return "暂无历史群聊消息"
        recent_msg = self.stream_msg[-max_msg_count:]
        messages_ = "\n".join(recent_msg)
        self.have_new_message = False
        return messages_
class ChatBotSession:
    def __init__(self,cfg,log,message_stream:MessageStreamObject,send_message_queue: asyncio.Queue):
        self.log = log
        self.cfg = cfg
        self.bot_id = uuid.uuid4()
        self.send_queue = send_message_queue
        self.message_stream = message_stream
        self.bot_action =[] #存储bot的行为记忆对象
        self.max_memory = self.cfg.get("setup","max_bot_memory")
        self.session_task = None
        self.is_running = False
    async def get_action_memory(self,max_memory:int = 15,llm_list:bool = False)->str|list:
        if not self.bot_action:
            return "暂无历史动作记忆"
        action_memory = []
        i = 0
        if not llm_list:
            for action in self.bot_action:
                memory:str = await action.get_until_action_memory()
                action_memory.append(memory)
            memories = "\n".join(action_memory[-max_memory:])
            return memories
        else:
            for action in self.bot_action[-max_memory:]:
                action_memory.append((None,await action.get_until_action_memory()))
            return action_memory

    async def run_session(self):
        self.is_running = True
        self.log.info(f"Session started for {self.bot_id}群id{self.message_stream.stream_id}")
        while self.is_running:
            if not self.message_stream.stream_msg or not self.message_stream.have_new_message:
                await asyncio.sleep(0.1)
                continue
            else:
                if random.random() < self.cfg.get("setup","probability_reply"): #概率回复
                    msg = await self.message_stream.get_new_message()
                    new_action = Action(cfg=self.cfg,log=self.log)
                    decision =await new_action.generate_decision(bot_session=self,chat_context=msg)
                    decision_dict=await new_action.parsing_decision(decision)
                    await new_action.execute_action(bot_session=self,chat_context=msg,decision=decision_dict)
                    self.bot_action.append(new_action)
                else:
                    await self.message_stream.get_new_message()
                    self.log.debug("概率，不回复")
                    await asyncio.sleep(0.1)
                    continue

    async def stop_session(self):
        """停止session任务"""
        self.is_running = False
        if self.session_task and not self.session_task.done():
            self.session_task.cancel()
            try:
                await self.session_task
            except asyncio.CancelledError:
                pass
        self.log.info(f"Session {self.bot_id} 已停止（群ID：{self.message_stream.stream_group_id}）")
class Action:
    def __init__(self,cfg,log):
        self.cfg = cfg
        self.log = log
        self.create_time = datetime.datetime.now()
        self.action_memory = ""
        self.tools = [
"SILENT | 静默观察 | 无合适动作/无需互动/群聊氛围不适合发言时 | 此动作不需要参数",
"REPLY | 文字回复 | 参与话题/回应通用提问/告知动作进度时 | 此动作不需要参数",
"SEARCHCOMIC | 搜索JM漫画 | 以关键字搜索JM中漫画并返回结果 | 参数：关键字 or JM号(不要有多余的输出如‘关键字’‘参数’等等)",
"DOWNLOADCOMIC | 下载JM漫画 | 下载特定ID的JM漫画并发送给用户 | 参数：JM号（一般为6位数的纯数字）"
]
        self.prompt= """过往记忆（你做过的事）
最近记忆：{{action_memory}}
记忆联动要求：
优先完成未完成的承诺或待办事项。
与用户互动时，风格需与过往保持一致。
若无相关记忆，则仅基于当前上下文决策。
当前群聊上下文（正在发生的事）
最新记录：{{chat_context}}
上下文要求：决策需贴合当前话题、氛围与对话对象，优先回应直接@、提问或提及你的用户，避免打断他人核心对话。
可用动作工具以及使用规则：
工具列表：{{tools}}
输出格式（严格遵循，不要输出多余的内容，仅输出以下内容）
【决策核心逻辑】（结合记忆、上下文与人设，以第一人称一句话总结你做了什么，为什么这么做，无多余文字/解释/换行）
【主动作】（工具标识）【决策依据】（选此动作的原因）【执行参数】（具体参数，无则填“无”）
【辅助动作】（工具标识/无）【决策依据】（原因/无）【执行参数】（参数/无）
【辅助动作】（工具标识/无）【决策依据】（原因/无）【执行参数】（参数/无)"""
    async def add_until_action_memory(self,decision:str):
        now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action_memory = f"[{now_str_time}]:{decision}]"
        self.action_memory=action_memory
    async def get_until_action_memory(self)->str:
        return self.action_memory

    async def parsing_decision(self,text:str)->dict:
        """
        严格解析指定格式文本，适配辅助动作0-2个、极简格式等所有缺失场景
        核心格式：
        【决策核心逻辑】决策依据
        【主动作】工具标识【决策依据】原因【执行参数】参数
        【辅助动作】工具标识【决策依据】原因【执行参数】参数（0-2个）
        :param text: 待解析文本（按行分隔，支持任意字段缺失）
        :return: 结构化字典，解析失败返回标准兜底值
        """
        # 你要求的【标准兜底字典】，一字不改，所有失败场景均返回此值
        DEFAULT_RESULT = {
            "decision_logic": "解析失败，无有效决策逻辑",
            "main_action": {"action": "SILENT", "reason": "无", "params": "无"},
            "aux_action1": {"action": "无", "reason": "无", "params": "无"},
            "aux_action2": {"action": "无", "reason": "无", "params": "无"}
        }

        try:
            # 步骤1：文本预处理 - 按行分割，过滤空行/纯空白行，去除每行首尾空白
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if not lines:  # 空文本直接兜底
                return DEFAULT_RESULT

            # 步骤2：逐行解析，提取标识和内容（按行匹配【xxx】，收集辅助动作列表）
            decision_logic = ""  # 决策核心逻辑内容
            main_action_content = ""  # 主动作原始内容
            aux_action_contents = []  # 辅助动作原始内容（按顺序收集，最多2个）

            for line in lines:
                # 格式校验：行必须以【开头且包含】，否则直接判定格式错误
                if not line.startswith("【") or "】" not in line:
                    return DEFAULT_RESULT
                # 仅分割第一个【】，避免内容中含【/】导致解析错乱
                mark_part, content_part = line.split("】", 1)
                mark = mark_part.replace("【", "").strip()  # 提取纯标识（无多余符号）
                content = content_part.strip()  # 提取标识后的纯内容

                # 按标识分类存储，辅助动作按出现顺序收集（最多2个）
                if mark == "决策核心逻辑":
                    decision_logic = content
                elif mark == "主动作":
                    main_action_content = content
                elif mark == "辅助动作":
                    if len(aux_action_contents) < 2:
                        aux_action_contents.append(content)

            # 步骤3：核心字段校验 - 必须同时有【决策核心逻辑】和【主动作】，否则兜底
            if not decision_logic or not main_action_content:
                return DEFAULT_RESULT

            # 步骤4：定义通用动作解析函数（主动作/辅助动作结构完全一致，统一解析）
            def parse_single_action(act_content):
                """
                解析单个动作内容，适配任意子项缺失，缺失部分自动补「无」
                输入：动作原始内容（如REPLY【决策依据】xxx【执行参数】无）
                输出：{action: 工具标识, reason: 决策依据, params: 执行参数}
                """
                # 初始化默认值，所有子项缺失时均为「无」
                action = "无"
                reason = "无"
                params = "无"

                # 第一步：分割【决策依据】，提取工具标识
                if "【决策依据】" in act_content:
                    action_part, rest_content = act_content.split("【决策依据】", 1)
                    action = action_part.strip() or "无"  # 工具标识为空则补「无」
                    # 第二步：分割【执行参数】，提取决策依据和执行参数
                    if "【执行参数】" in rest_content:
                        reason_part, params_part = rest_content.split("【执行参数】", 1)
                        reason = reason_part.strip() or "无"
                        params = params_part.strip() or "无"
                    else:
                        reason = rest_content.strip() or "无"  # 无【执行参数】则剩余内容为决策依据
                else:
                    action = act_content.strip() or "无"  # 无【决策依据】则全部内容为工具标识

                return {"action": action, "reason": reason, "params": params}

            # 步骤5：解析所有动作（适配辅助动作0-2个的场景）
            main_action = parse_single_action(main_action_content)
            # 辅助动作1：有则解析，无则返回默认无值
            aux_action1 = parse_single_action(aux_action_contents[0]) if len(aux_action_contents) >= 1 else {"action": "无", "reason": "无", "params": "无"}
            # 辅助动作2：有则解析，无则返回默认无值
            aux_action2 = parse_single_action(aux_action_contents[1]) if len(aux_action_contents) >= 2 else {"action": "无", "reason": "无", "params": "无"}

            # 步骤6：组装最终解析结果
            return {
                "decision_logic": decision_logic,
                "main_action": main_action,
                "aux_action1": aux_action1,
                "aux_action2": aux_action2
            }

        # 捕获所有解析异常（分割错误、索引越界、格式异常等），统一返回标准兜底
        except Exception:
            return DEFAULT_RESULT
    async def generate_decision(self,chat_context:str,bot_session:ChatBotSession):
        """
                生成决策核心方法：拼接Prompt→调用LLM→返回原始决策响应
                :param chat_context:
                :param bot_session: 机器人会话对象（提供记忆/上下文/人设）
                :return: LLM返回的原始决策字符串，异常则返回空字符串
                """
        try:
            self.log.info(f"开始为会话{bot_session.bot_id}生成动作决策")
            # 1. 准备三大核心原料：格式化记忆/聊天上下文/工具列表
            # 1.1 格式化过往记忆
            action_memory = await bot_session.get_action_memory()
            # 1.2 构建并格式化当前群聊上下文（取最新N条，配置可配，默认15条）
            # 1.3 格式化工具列表（直接拼接self.tools）
            tools = "\n".join(self.tools)

            # 2. 填充Prompt占位符（替换{{}}为实际内容）
            full_prompt = self.prompt.replace("{{action_memory}}", action_memory) \
                .replace("{{chat_context}}", chat_context) \
                .replace("{{tools}}", tools)
            self.log.debug(f"决策Prompt构建完成（前500字符）：{full_prompt[:500]}...")

            # 3. 调用项目现有LLM API（复用UseAPI，和ChatBotSession的调用逻辑完全一致）
            llm_response = await UseAPI(
                current_uesrmsg=full_prompt,
                model=self.cfg.get("openai", "model"),
                global_cfg=self.cfg,
                llm_role=self.cfg.get("setup", "setting")  # 复用人设，保证行为一致性
            )

            if not llm_response:
                self.log.warning(f"会话{bot_session.bot_id}的LLM响应为空")
                return ""
            self.log.debug(f"会话{bot_session.bot_id}获取LLM决策响应：{llm_response[:300]}...")
            return llm_response
        except Exception as e:
            self.log.error(f"为会话{bot_session.bot_id}生成决策失败：{str(e)}", exc_info=True)
            return ""
    async def execute_action(self,bot_session:ChatBotSession,decision:dict,chat_context:str):
        """
        执行决策的动作：按【主动作→辅助动作1→辅助动作2】顺序执行，调用对应动作方法
        :param chat_context:
        :param bot_session: 机器人会话对象（提供执行所需的群ID/发送队列等）
        :param decision: parsing_decision返回的结构化决策字典
        :return: 无返回值，异常时记录日志并继续执行下一个动作
        """
        try:
            self.log.info(f"开始为会话{bot_session.bot_id}执行动作决策，核心逻辑：{decision['decision_logic'][:50]}...")
            # 1. 提取动作列表（按执行优先级排序）
            actions = [
                ("主动作", decision["main_action"]),
                ("辅助动作1", decision["aux_action1"]),
                ("辅助动作2", decision["aux_action2"])
            ]
            #group_id = bot_session.message_stream.stream_group_id  # 获取执行的群ID

            # 2. 按顺序执行每个动作
            for action_type, action_info in actions:
                act = action_info["action"]
                act_reason = action_info["reason"]
                act_params = action_info["params"]

                # 跳过无效动作（空/静默观察）
                if not act or "SILENT" in act:
                    self.log.debug(f"跳过{action_type}：{act or '无'}")
                    continue

                # 3. 执行有效动作：调用对应动作方法，传递参数和群ID
                self.log.info(f"执行{action_type}：{act} | 依据：{act_reason[:30]}... | 参数：{act_params[:50]}...")
                try:
                    if "REPLY" in act:
                        # 文字回复：调用reply_action，传递执行参数和群ID
                        await self.reply_action(bot_session=bot_session,chat_context=chat_context,inner_os=act_reason)
                    elif "SEARCHCOMIC" in act:
                        await self.search_comic_action(comic_keyword=act_params,bot_session=bot_session)
                    elif"DOWNLOADCOMIC" in act:
                        await self.download_comic_action(bot_session=bot_session,comic_id=act_params)
                    else:
                        self.log.warning(f"不支持的动作类型：{act}，跳过执行")
                    #4.创建历史动作记忆
                    await self.add_until_action_memory(decision['decision_logic'])
                except Exception as e:
                    self.log.error(f"{action_type}{act}执行失败：{str(e)}", exc_info=True)
                    continue  # 单个动作失败，不影响其他动作执行

            self.log.info(f"会话{bot_session.bot_id}的动作决策执行完成")
        except Exception as e:
            self.log.error(f"执行动作决策总流程失败：{str(e)}", exc_info=True)

    async def reply_action(self,bot_session:ChatBotSession,chat_context,inner_os:str):
        """

        :return: 返回动作的完成状态
        """
        template_msg = f"""你注意到了这个群聊，该群聊的聊天记录如下：
{chat_context}
你现在正在想：{inner_os}
基于聊天记录的语境和角色身份以及过往内心心理记忆，生成一句符合人设的**群聊回复**；
回复需口语化，符合日常群聊的说话习惯，不要输出多余的内容比如：(动作描述)仅输出要回复的内容"""
        try:
            # 获取ai的实际回复
            response = await UseAPI(current_uesrmsg=template_msg,
                                    model=self.cfg.get("openai", "model"),
                                    history=await bot_session.get_action_memory(llm_list=True),
                                    global_cfg=self.cfg,
                                    llm_role=self.cfg.get("setup", "setting"))

            #创建消息，
            new_group_msg = Group_Msg(group_id=bot_session.message_stream.stream_group_id,)
            await new_group_msg.build_text_msg(text=response)
            payload:dict = dict(await new_group_msg.return_complete_http_payload())
            #放入消息发送队列
            await bot_session.send_queue.put(payload)
            # 获取自己的消息
            now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alias_name = self.cfg.get("setup", "alias_name")
            str_msg = f"{now_str_time} [{alias_name}]: {response}"  # 将ai的回复添加进聊天流
            await bot_session.message_stream.add_new_message(str_msg, self_add=True)
            self.log.info(f"Session {bot_session.bot_id} 消息：{response}...")
        except Exception as e:
            self.log.error(f"Session {bot_session.bot_id} 处理消息失败：{e}", exc_info=True)
            self.log.error(f"{e}")
    async def search_comic_action(self,bot_session:ChatBotSession,comic_keyword:str|int):
        text = search_comic(comic_keyword=comic_keyword)
        # 创建消息，
        new_group_msg = Group_Msg(group_id=bot_session.message_stream.stream_group_id, )
        await new_group_msg.build_text_msg(text=text)
        payload: dict = await new_group_msg.return_complete_websocket_payload()
        # 选择发送方式
        send_msg = choice_send_tpye(payload=payload, send_type="websocket")
        # 放入消息发送队列
        await bot_session.send_queue.put(send_msg)
        # 获取自己的消息
        now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        alias_name = self.cfg.get("setup", "alias_name")
        str_msg = f"{now_str_time} [{alias_name}]: {text}"  # 将ai的回复添加进聊天流
        await bot_session.message_stream.add_new_message(str_msg, self_add=True)
        self.log.info(f"Session {bot_session.bot_id} 消息：{text}...")
    async def silent_action(self,):
        pass
    async def download_comic_action(self,bot_session:ChatBotSession,comic_id:int):
        file_data = download_comics(comic_id=comic_id)
        if file_data:
            new_group_msg = Group_Msg(group_id=bot_session.message_stream.stream_group_id, )
            await new_group_msg.build_file_msg(file_name=str(comic_id),file=file_data)
            payload: dict = await new_group_msg.return_complete_http_payload()
            #选择发送方式
            send_msg =choice_send_tpye(payload=payload,send_type="http")
            # 放入消息发送队列
            await bot_session.send_queue.put(send_msg)
            # 获取自己的消息
            now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alias_name = self.cfg.get("setup", "alias_name")
            str_msg = f"{now_str_time} [{alias_name}]: [发送了一个{comic_id}.pdf文件]"  # 将ai的回复添加进聊天流
            await bot_session.message_stream.add_new_message(str_msg, self_add=True)
            self.log.info(f"Session {bot_session.bot_id} 消息：{comic_id}.pdf文件正在发送")
        else:
            self.log.warning("文件不存在")
class Bot:
    def __init__(self, log,cfg, message_queue: asyncio.Queue, send_message_queue: asyncio.Queue):
        self.log = log
        self.cfg = cfg
        self.message_queue = message_queue  # 注入全局队列
        self.send_message_queue = send_message_queue
        self.is_running = True  # 控制消费循环
        self.bot_session: dict[MessageStreamObject, tuple[ChatBotSession,asyncio.Task]] = {} #存储chatbot对象
        self.msg_stream:list[MessageStreamObject] = [] #存储消息流

    async def test_Stream_msg(self):
        """完善：打印所有消息流的详细信息（按群分类）"""
        self.log.info("===== 开始打印所有消息流 =====")
        if not self.msg_stream:
            self.log.info("暂无消息流数据")
            return

        for stream in self.msg_stream:
            # 打印消息流基本信息
            self.log.info(
                f"【群ID: {stream.stream_group_id}】消息流ID: {stream.stream_id} | 创建时间: {datetime.datetime.fromtimestamp(stream.crate_time).strftime('%Y-%m-%d %H:%M:%S')} | 消息数: {len(stream.stream_msg)}")
            # 打印该群的每条消息
            for idx, msg in enumerate(stream.stream_msg, 1):
                self.log.info(f"  消息{idx}: {msg}")
        self.log.info("===== 消息流打印结束 =====\n")
    async def ensure_session_active(self, stream: MessageStreamObject):
        """确保消息流对应的Session已激活（仅创建一次）"""
        if stream in self.bot_session:
            # 检查现有Session是否正常运行
            session, task = self.bot_session[stream]
            if task.done() and not session.is_running:
                self.log.info(f"群{stream.stream_group_id}的Session已终止，重新启动")
                await self.create_and_start_bot_session(stream)
            return

        # 新消息流：创建并启动Session
        await self.create_and_start_bot_session(stream)
    async def message_handle(self, msg: dict):
        """处理具体消息根据消息的群聊id分类放进消息流对象"""
        try:
            message_type = msg.get("message_type")
            # 目前只支持群聊消息
            if message_type == "group":
                messages: list = msg.get("message", [])
                group_id = msg.get("group_id")

                # 前置校验：无群ID则跳过（核心字段缺失）
                if not group_id:
                    self.log.warning("消息缺少group_id，跳过处理")
                    return

                # 拼接纯文本消息
                text_message = ""
                for message_dict in messages:
                    if message_dict.get("type") == "text":
                        data = message_dict.get("data", {})
                        text_val = data.get("text", "")
                        text_message += text_val
                    if message_dict.get("type") == "image":
                        data = message_dict.get("data", {})

                        if data.get("sub_type") == 0: #图片消息
                            text_requirement = """请你准确的以自然语言的形式，用一段话，描述这张图片的主体和画面，将图片的特征描述出来，严禁多余的输出如：提示文明使用表情包的输入等等"""
                            image_url = data.get("url")
                            content = build_llm_vision_content(image_urls=image_url,text=text_requirement)
                            response = await UseAPI(current_uesrmsg=content,model=self.cfg.get("openai","model_vision"),global_cfg=self.cfg)
                            text_message += f"[发送一个了图片消息]：{response}"
                        elif data.get("sub_type") == 1: #表情包消息
                            text_requirement = """请你准确的以自然语言的形式，用一段话，描述这张表情包表达了什么，解释它有什么梗或者含义，严禁多余的输出如：提示文明使用表情包的输入等等"""
                            image_url = data.get("url")
                            content = build_llm_vision_content(image_urls=image_url, text=text_requirement)
                            response = await UseAPI(current_uesrmsg=content,
                                                    model=self.cfg.get("openai", "model_vision"),global_cfg=self.cfg)
                            text_message += f"[发送一个了表情包消息]：{response}"
                        else:
                            self.log.warning(f"未知的消息类型{data.get('sub_type')}")
                    else:
                        self.log.debug(f"暂不支持的消息段类型：{message_dict.get('type')}")
                # 构造格式化消息
                send_time = msg.get("time", datetime.datetime.now().timestamp())
                nickname = msg.get("sender", {}).get("nickname", "unknown")
                role = msg.get("sender", {}).get("role", "member")
                # 修正发送者身份
                for role_map in MessageStreamObject.GROUP_ROLE:
                    if role in role_map:
                        role = role_map[role]
                        break
                now_str_time = datetime.datetime.fromtimestamp(send_time).strftime("%Y-%m-%d %H:%M:%S")
                str_msg = f"{now_str_time} [{nickname}]-[{role}]: {text_message}"

                # 查找/创建消息流
                target_stream = None
                for stream in self.msg_stream:
                    if stream.stream_type == MessageStreamObject.GROUP and stream.stream_group_id == group_id:
                        target_stream = stream
                        break
                #指令调试
                self.log.debug(f"text_message: {text_message}")
                if await self.command_debug(text_message,target_stream):
                    return

                if not target_stream:
                    target_stream = MessageStreamObject(
                        group_id=group_id,
                        stream_type=MessageStreamObject.GROUP
                    )
                    self.msg_stream.append(target_stream)
                    self.log.info(f"为群{group_id}创建新消息流")

                # 追加消息并标记有新消息
                await target_stream.add_new_message(str_msg)  # 改用async方法（原代码是直接append，需保持async）
                self.log.debug(f"群{group_id}消息已存入流：{str_msg}")

                # 为新消息流创建并启动Session（核心：激活Session）
                await self.ensure_session_active(target_stream)
            else:
                self.log.debug(f"暂不支持的消息类型：{message_type}，仅支持群聊消息")
        except Exception as e:
            self.log.error(f"消息处理失败：msg={msg} | 错误详情：{str(e)}", exc_info=True)
    async def command_debug(self, msg:str, stream_obj:MessageStreamObject) -> bool:
        self.log.info(f"目前聊天流共有{len(self.msg_stream)}个，bot有{len(self.bot_session)}")
        if msg == "/view_stream_msg":
            self.log.info("===== 开始打印所有消息流 =====")
            if not self.msg_stream:
                self.log.info("暂无消息流数据")
                return True
            session, task = self.bot_session.get(stream_obj)

            for stream in self.msg_stream:
                # 打印消息流基本信息
                self.log.info(
                    f"【群ID: {stream.stream_group_id}】消息流ID: {stream.stream_id} | 创建时间: {datetime.datetime.fromtimestamp(stream.crate_time).strftime('%Y-%m-%d %H:%M:%S')} | 消息数: {len(stream.stream_msg)}")
                await session.send_text_message(text=f"【群ID: {stream.stream_group_id}】消息流ID: {stream.stream_id} | 创建时间: {datetime.datetime.fromtimestamp(stream.crate_time).strftime('%Y-%m-%d %H:%M:%S')} | 消息数: {len(stream.stream_msg)}", group_id=stream_obj.stream_group_id)
                # 打印该群的每条消息
                for idx, msg in enumerate(stream.stream_msg, 1):
                    await session.send_text_message(text=f"消息{idx}: {msg}", group_id=stream_obj.stream_group_id)
                    self.log.info(f"  消息{idx}: {msg}")
            self.log.info("===== 消息流打印结束 =====\n")
            return True
        if msg == "/view_stream_inner_os":
            session, task = self.bot_session.get(stream_obj)
            for bot_session,task in self.bot_session.values():
                self.log.debug(f"当前机器人:{bot_session.bot_id}的内心os如下：")
                await session.send_text_message(text=f"当前机器人:{bot_session.bot_id}的内心os如下：",group_id=stream_obj.stream_group_id)
                for action in bot_session.bot_action:
                    action_str = action.action_memory
                    await session.send_text_message(text=action_str,group_id=stream_obj.stream_group_id)
                    self.log.debug(f"{action_str}")
            return True
        self.log.debug("未找到指令")
        return False
    async def create_and_start_bot_session(self,message_stream:MessageStreamObject):
        session = ChatBotSession(cfg=self.cfg,log=self.log,message_stream=message_stream,send_message_queue=self.send_message_queue)
        session_task = asyncio.create_task(session.run_session())
        self.bot_session[message_stream] = (session,session_task)
        self.log.info(f"ChatbotSession-{session.bot_id}对象已创建并激活")
    async def run(self):
        """启动Bot消息消费循环"""
        self.log.info("Bot开始消费消息...")
        try:
            while self.is_running:
                # 阻塞等待队列消息，超时避免死等（可调整）
                try:
                    msg = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                    await self.message_handle(msg)
                    # 标记消息处理完成（队列任务追踪）
                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    continue  # 超时继续循环，检测是否需要退出
        except asyncio.CancelledError:
            self.log.info("Bot消费任务被取消，正在退出")
            self.is_running = False
        finally:
            self.log.info("Bot已停止消费消息")