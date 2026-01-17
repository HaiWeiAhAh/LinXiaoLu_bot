# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import uuid

from pyexpat.errors import messages

from src.LLM_API import UseAPI

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
    ROLE_MEMBER = {"member":"群臣员"}
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
    async def get_new_message(self) -> str:
        messages_ =""
        for msg in self.stream_msg:
            messages_ = messages_+"\n"+msg
        self.have_new_message = False
        return messages_
class ChatBotSession:
    def __init__(self,cfg,log,message_stream:MessageStreamObject,send_message_queue: asyncio.Queue):
        self.log = log
        self.cfg = cfg
        self.bot_id = uuid.uuid4()
        self.send_queue = send_message_queue
        self.message_stream = message_stream
        self.session_task = None
        self.is_running = False
    async def start_session(self):
        self.is_running = True
        self.log.info(f"Session started for {self.bot_id}群id{self.message_stream.stream_id}")
        while self.is_running:
            if self.message_stream.stream_msg:
                continue
            if not self.message_stream.have_new_message:
                await asyncio.sleep(0.1)
            if self.message_stream.have_new_message:
                msg = await self.message_stream.get_new_message()
                template_msg = f"""QQ铃声的振动引起了你的注意，看到了这个群聊的天记录如下
{msg}
对此你想说（或者不想说）："""
                try:
                    response = await UseAPI(current_uesrmsg=template_msg,global_cfg=self.cfg)
                    await self.send_text_message(
                        text=response,
                        group_id=self.message_stream.stream_group_id
                    )
                    #获取自己消息的
                    now_str_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    alias_name = self.cfg.get("setup","alias_name")
                    str_msg = f"{now_str_time} [{alias_name}]: {response}"#将ai的回复添加进聊天流
                    await self.message_stream.add_new_message(str_msg,self_add=True)
                    self.log.info(f"Session {self.bot_id} 已处理消息并回复：{response[:50]}...")
                except Exception as e:
                    self.log.error(f"Session {self.bot_id} 处理消息失败：{e}", exc_info=True)
                    self.log.error(f"{e}")

    async def send_text_message(self,text:str,group_id:int):
        self.log.info("尝试发送消息到adapter")
        payload = {"text": text, "group_id": group_id}
        await self.send_queue.put(payload)

    async def stop_session(self):
        pass
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
    async def message_handle(self, msg: dict):
        """处理具体消息根据消息的群聊id分类放进消息流对象"""
        try:
            message_type = msg.get("message_type")
            # 目前只支持群聊消息
            if message_type == "group":
                # 修复1：给msg.get加默认值，避免messages为None导致遍历报错
                messages: list = msg.get("message", [])
                group_id = msg.get("group_id")

                # 前置校验：无群ID则跳过（核心字段缺失）
                if not group_id:
                    self.log.warning("消息缺少group_id，跳过处理")
                    return

                text_message = ""
                # 目前只支持纯文本消息
                for message_dict in messages:
                    if message_dict.get("type") == "text":
                        # 修复2：逐层加默认值，避免data/text为None
                        data = message_dict.get("data", {})
                        text_val = data.get("text", "")
                        text_message += text_val  # 等价于 text_message = text_message + text_val
                    else:
                        self.log.debug(f"暂不支持的消息段类型：{message_dict.get('type')}")

                # 修复3：处理time/nickname空值，加默认值兜底
                send_time = msg.get("time", datetime.datetime.now().timestamp())  # 无time则用当前时间
                nickname = msg.get("sender").get("nickname","unknown")  # 无nickname则兜底
                role = msg.get("sender").get("role")
                #修正消息发送者的身份
                for roles in MessageStreamObject.GROUP_ROLE:
                    if role in roles.keys():
                        role = roles[role]
                now_str_time = datetime.datetime.fromtimestamp(send_time).strftime("%Y-%m-%d %H:%M:%S")
                str_msg = f"{now_str_time} [{nickname}]-[{role}]: {text_message}"

                # 修复4：重构消息流查找逻辑（核心！）
                # 步骤1：先遍历所有流，找匹配的群ID
                target_stream = None
                for stream in self.msg_stream:
                    if stream.stream_type == MessageStreamObject.GROUP and stream.stream_group_id == group_id:
                        target_stream = stream
                        break  # 找到后立即退出循环，避免无效遍历

                # 步骤2：未找到匹配的流，才创建新流
                if not target_stream:
                    # 修复5：stream_type传正确的常量，拼写修正crate→create
                    create_stream = MessageStreamObject(
                        group_id=group_id,
                        stream_type=MessageStreamObject.GROUP  # 关键：用常量而非字符串
                    )
                    self.msg_stream.append(create_stream)
                    target_stream = create_stream  # 指向新流，统一后续追加逻辑
                    self.log.info(f"为群{group_id}创建新消息流")

                # 步骤3：统一追加消息（无论流是已存在还是新创建）
                target_stream.stream_msg.append(str_msg)
                self.log.debug(f"群{group_id}消息已存入流：{str_msg}")
            else:
                self.log.debug(f"暂不支持的消息类型：{message_type}，仅支持群聊消息")
        except Exception as e:
            # 新增：捕获所有异常，记录详细日志
            self.log.error(f"消息处理失败：msg={msg} | 错误详情：{str(e)}", exc_info=True)

    async def create_and_start_bot_session(self,message_stream:MessageStreamObject):
        session = ChatBotSession(cfg=self.cfg,log=self.log,message_stream=message_stream,send_message_queue=self.send_message_queue)
        session_task = asyncio.create_task(session.start_session())
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
                    #打印聊天流
                    if time.time() - last_print_time >= print_interval:
                        await self.test_Stream_msg()
                        last_print_time = time.time()
                    #为聊天流创建聊天对象,并激活
                    for stream in self.msg_stream:
                        if not stream in self.bot_session:
                            await self.create_and_start_bot_session(message_stream=stream)
                    self.log.info(f"目前聊天流共有{len(self.msg_stream)}个，bot有{len(self.bot_session)}")
                except asyncio.TimeoutError:
                    continue  # 超时继续循环，检测是否需要退出
        except asyncio.CancelledError:
            self.log.info("Bot消费任务被取消，正在退出")
            self.is_running = False
        finally:
            self.log.info("Bot已停止消费消息")


