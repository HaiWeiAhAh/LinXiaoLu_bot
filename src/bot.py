# -*- coding: utf-8 -*-
import asyncio
import datetime
import re
import time
import uuid
import random
from functools import wraps
from src.LLM_API import UseAPI,build_llm_vision_content


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
        messages_ =""
        if not isinstance(max_msg_count, int) or max_msg_count <= 0:
            max_msg_count = 15
        if not self.have_new_message:
            return ""
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
        self.bot_action_memory =[] #存储bot的行为记忆
        self.max_memory = self.cfg.get("setup","max_bot_memory")
        self.session_task = None
        self.is_running = False
    async def build_action_memory_unit(self,action:str):
        now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        action_memory = f"[{now_str_time}]:{action}]"
        self.bot_action_memory.append(("",action_memory))
    async def get_action_memory(self,max_memory:int = 15)->list:
        """目前用不了"""
        return self.bot_action_memory[-max_memory]
    async def run_session(self):
        self.is_running = True
        self.log.info(f"Session started for {self.bot_id}群id{self.message_stream.stream_id}")
        while self.is_running:
            if not self.message_stream.stream_msg or not self.message_stream.have_new_message:
                await asyncio.sleep(0.1)
                continue
            else:
                if random.random() < self.cfg.get("setup","probability_reply"): #概率回复
                    await self.reply()
                else:
                    msg = await self.message_stream.get_new_message()
                    self.log.debug("概率，不回复")
                    await asyncio.sleep(0.1)
                    continue

    async def reply(self):
        msg = await self.message_stream.get_new_message()
        template_msg = f"""你注意到了这个群聊，该群聊的聊天记录如下：
            {msg}
            请你完成以下两项任务，输出格式严格遵循要求：
            1.  基于聊天记录的语境和角色身份以及过往内心心理记忆，生成一句符合人设的**群聊回复**；
            2.  以第一人称视角，撰写一段**内心想法（内心OS）**，想法要贴合角色当下的真实心理活动，和实际回复可以存在反差或呼应。
            输出格式要求：
            【实际回复】：[这里填写符合角色身份的群聊回复内容]
            【内心OS】：[这里填写第一人称的真实内心想法]
            额外约束：
            内心OS和实际回复的语气可以不一致，想法要真实直白，不用刻意迎合群聊氛围；
            回复和想法均需口语化，符合日常群聊的说话习惯。"""
        try:
            # 获取ai的内心活动和实际回复
            response = await UseAPI(current_uesrmsg=template_msg,
                                    model=self.cfg.get("openai", "model"),
                                    history=self.bot_action_memory[-self.max_memory:],
                                    global_cfg=self.cfg,
                                    llm_role=self.cfg.get("setup", "setting"))
            # 区分ai的内心活动和实际回复
            result = {}
            patterns = {
                'actual_reply': r'【实际回复】\s*[:：]\s*(.+)',
                'inner_os': r'【内心OS】\s*[:：]\s*(.+)',
            }
            for key, pattern in patterns.items():
                match = re.search(pattern, response)
                if match:
                    result[key] = match.group(1).strip()
                else:
                    result[key] = ""
            await self.build_action_memory_unit(result["inner_os"])
            await self.send_text_message(
                text=result["actual_reply"],
                group_id=self.message_stream.stream_group_id
            )
            # 获取自己消息的
            now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alias_name = self.cfg.get("setup", "alias_name")
            str_msg = f"{now_str_time} [{alias_name}]: {result['actual_reply']}"  # 将ai的回复添加进聊天流
            await self.message_stream.add_new_message(str_msg, self_add=True)
            self.log.info(f"Session {self.bot_id} 消息：{response}...")
        except Exception as e:
            self.log.error(f"Session {self.bot_id} 处理消息失败：{e}", exc_info=True)
            self.log.error(f"{e}")
    async def send_text_message(self,text:str,group_id:int):
        self.log.info("尝试发送消息到adapter")
        payload = {"text": text, "group_id": group_id}
        await self.send_queue.put(payload)
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
    def __init__(self,cfg,log,message_stream:MessageStreamObject):
        self.cfg = cfg
        self.log = log
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
                for msg in bot_session.bot_action_memory:
                    user,action_memory = msg
                    await session.send_text_message(text=action_memory,group_id=stream_obj.stream_group_id)
                    self.log.debug(action_memory)
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
        print_interval = 30  # 30秒打印一次
        last_print_time = time.time()
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


