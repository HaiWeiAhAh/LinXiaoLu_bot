# -*- coding: utf-8 -*-
import asyncio
import datetime
import time
import uuid


class MessageStreamObject:
    """
    :用于napcat的聊天流对象
    :argument 用于保存聊天记录和管理消息
    :example 以消息列表的形式表达
    ["2026-1-1 22:11:10 '小吕':‘什么贵，你知道吗’","2026-1-1 22:12:10 '小鹿':‘不知道’","2026-1-1 22:14:10 '小吕':‘太逊了’"]
    """


    GROUP = "group"
    STREAM_TYPE = [GROUP]


    def __init__(self,group_id:int =None,stream_type:str=None):
        self.crate_time = time.time()
        self.stream_id = uuid.uuid4()
        self.stream_name: str = ""
        self.stream_msg: list = []  # 这里放置受到的群聊消息
        self.stream_type = stream_type
        self.stream_group_id = group_id


class Bot:
    def __init__(self, log, message_queue: asyncio.Queue):
        self.log = log
        self.message_queue = message_queue  # 注入全局队列
        self.is_running = True  # 控制消费循环
        self.msg_stream:list[MessageStreamObject] = [] #存储消息流

    async def testStreammsg(self):
        """完善：打印所有消息流的详细信息（按群分类）"""
        self.log.info("===== 开始打印所有消息流 =====")
        if not self.msg_stream:
            self.log.info("暂无消息流数据")
            return

        for stream in self.msg_stream:
            # 打印消息流基本信息
            self.log.info(
                f"【群ID: {stream.stream_group_id}】消息流ID: {stream.stream_id} | 创建时间: {datetime.datetime.fromtimestamp(stream.create_time).strftime('%Y-%m-%d %H:%M:%S')} | 消息数: {len(stream.stream_msg)}")
            # 打印该群的每条消息
            for idx, msg in enumerate(stream.stream_msg, 1):
                self.log.info(f"  消息{idx}: {msg}")
        self.log.info("===== 消息流打印结束 =====\n")
    async def message_handle(self, msg: dict):
        """处理具体消息根据消息的群聊id分类放进消息流对象"""
        message_type = msg.get("message_type")
        #目前只支持群聊消息
        if message_type == "group":
            messages:list = msg.get("message")
            group_id = msg.get("group_id")
            text_message = ""
            #目前只支持纯文本消息
            for message_dict in messages:
                if message_dict.get("type") == "text":
                    text_message = text_message + message_dict.get("data").get("text")
                else:
                    self.log.debug("消息类型目前不支持")
            #转换格式变成str的格式
            now_str_time= datetime.datetime.fromtimestamp(msg.get("time")).strftime("%Y-%m-%d %H:%M:%S")
            nickname = msg.get("nickname")
            str_msg = f"{now_str_time} [{nickname}]:{text_message}"


            #寻找适配的消息流放入
            for stream in self.msg_stream:
                if stream.stream_type == MessageStreamObject.GROUP:
                    if stream.stream_group_id == group_id:
                        stream.stream_msg.append(str_msg)
                    else:
                        #找不到适配的聊天流，创建一个新的聊天流
                        crate_stream = MessageStreamObject(group_id=group_id, stream_type="message_type")
                        self.msg_stream.append(crate_stream)
                        crate_stream.stream_msg.append(str_msg)
        else:
            self.log.debug("消息类型目前不支持")
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

                    if time.time() - last_print_time >= print_interval:
                        await self.testStreammsg()
                        last_print_time = time.time()
                except asyncio.TimeoutError:
                    continue  # 超时继续循环，检测是否需要退出
        except asyncio.CancelledError:
            self.log.info("Bot消费任务被取消，正在退出")
            self.is_running = False
        finally:
            self.log.info("Bot已停止消费消息")


