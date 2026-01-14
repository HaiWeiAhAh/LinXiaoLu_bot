# -*- coding: utf-8 -*-
import asyncio
import sys
import json
import websockets as Server

local_message_queue = asyncio.Queue()

class Adapter:
    def __init__(self,cfg,log,global_message_queue):
        self.cfg = cfg
        self.log = log
        self.host = cfg.get("adapter", "host")
        self.port = cfg.get("adapter", "port")

        self.message_queue = global_message_queue#传递napcat消息
        self.server = None


    async def message_recv(self,server_connection: Server.ServerConnection):
        async for raw_message in server_connection:
            self.log.info(
                f"{raw_message[:100]}..."
                if (len(raw_message) > 100)
                else raw_message
            )
            decoded_raw_message: dict = json.loads(raw_message)
            post_type = decoded_raw_message.get("post_type")
            if post_type in ["message"]:
                await self.message_queue.put(decoded_raw_message)
            elif post_type is None:
                pass #修改点



    async def start_server(self):
        try:
            self.log.info("正在启动adapter...")
            async with Server.serve(self.message_recv,host=self.host,port=self.port) as self.server:
                self.log.info(
                    f"Adapter已启动，监听地址: ws://{self.host}:{self.port}"
                )
                await self.server.serve_forever()
        except asyncio.CancelledError:
            self.log.info("Adapter服务收到取消信号，正在关闭")
            if self.server:
                self.server.close()
                await self.server.wait_closed()
        finally:
            self.log.info("Adapter服务已关闭")
