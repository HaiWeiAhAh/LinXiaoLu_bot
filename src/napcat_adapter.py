# -*- coding: utf-8 -*-
import asyncio
import json
import uuid
from typing import Any

import websockets as Server

send_message_queue = asyncio.Queue()

class Adapter:
    def __init__(self,cfg,log,global_message_queue,global_send_queue):
        self.cfg = cfg
        self.log = log
        self.host = cfg.get("adapter", "host")
        self.port = cfg.get("adapter", "port")

        self.active_connections = set()
        self.message_queue = global_message_queue#接受napcat消息并向bot转发消息的队列
        self.send_msg_queue = global_send_queue
        self.server = None
        self.response_queue = []

    async def put_response(self,response:dict):
        self.response_queue.append(response)

    async def get_response(self,request_id: str) -> Any | None:
        retry_count = 0
        retry_count_2=0
        max_retries = 50  # 10秒超时
        await asyncio.sleep(0.2)

        while self.response_queue is None:
            retry_count += 1
            if retry_count >= max_retries:
                raise TimeoutError("请求超时，未收到响应")
            await asyncio.sleep(0.2)

        while self.response_queue is not None:
            for response in self.response_queue:
                if response.get("echo") == request_id:
                    response = self.response_queue.pop(0)
                    return response
            retry_count_2 += 1
            if retry_count_2 >= max_retries:
                raise TimeoutError(f"请求超时，未找到响应{request_id}")
            await asyncio.sleep(0.2)

    async def get_send_msg_to_napcat(self):
        """循环从Bot中取出消息交给其他方法处理"""
        while True:
            try:
                # 修复：使用重命名后的队列，且超时时间内检测取消信号
                payload: dict = await asyncio.wait_for(
                    self.send_msg_queue.get(), timeout=1.0
                )
                self.send_msg_queue.task_done()
                #标记消息
                request_uuid = str(uuid.uuid4())
                conn = next(iter(self.active_connections))
                await conn.send(dict(payload))
                #获取消息响应
                try:
                    response = await self.get_response(request_uuid)
                    if response.get("status") == "ok":
                        self.log.info("消息发送成功")
                    else:
                        self.log.warning(f"消息发送失败，napcat返回：{str(response)}")
                except TimeoutError:
                    self.log.error("发送消息超时，未收到响应")
                    response = {"status": "error", "message": "timeout"}
                except Exception as e:
                    self.log.error(f"发送消息错误{e}")
            except asyncio.TimeoutError:
                continue  # 超时继续，检测是否需要退出
            except asyncio.CancelledError:
                self.log.info("发送消息循环收到取消信号，退出")
                break
            except Exception as e:
                self.log.error(f"处理发送队列消息错误: {e}")

    async def message_recv(self, server_connection: Server.ServerConnection):
        self.active_connections.add(server_connection)
        try:
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
                    await self.put_response(decoded_raw_message)
        finally:
            self.active_connections.discard(server_connection)
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