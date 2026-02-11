# -*- coding: utf-8 -*-
import asyncio
import json
import uuid
from typing import Any

import aiohttp
import websockets as Server


class Adapter:
    def __init__(self, cfg, log, global_message_queue, global_send_queue, global_response_queue):
        self.cfg = cfg
        self.log = log
        self.host = cfg.get("adapter", "host")
        self.port = cfg.get("adapter", "port")
        self.http_server_ip = cfg.get("adapter", "server_ip")
        self.http_server_port = cfg.get("adapter", "server_port")

        self.active_connections = set()
        self.message_queue = global_message_queue  # 接受napcat消息并向bot转发消息的队列
        self.send_msg_queue = global_send_queue  # 从bot接收待发送消息的队列
        self.send_response_queue = global_response_queue  # 向bot回传发送结果的队列
        self.server = None
        self.response_queue = []  # 临时存储napcat的响应，用于匹配request_id

    async def put_response(self, response: dict):
        """添加napcat的响应到临时队列，供get_response匹配"""
        self.response_queue.append(response)

    async def get_response(self, request_id: str) -> Any |None:
        """根据request_id从响应队列中获取匹配的响应，超时返回None"""
        retry_count = 0
        max_retries = 50  # 每次sleep 0.2秒，总计10秒超时
        # 移除无效的None判断，直接循环匹配
        while retry_count < max_retries:
            # 遍历响应队列，找到匹配的响应
            for idx, response in enumerate(self.response_queue):
                if response.get("echo") == request_id:
                    # 移除并返回匹配的响应（修正pop(0)的错误）
                    matched_response = self.response_queue.pop(idx)
                    return matched_response
            # 未找到则等待并重试
            retry_count += 1
            await asyncio.sleep(0.2)

        # 超时未找到
        raise TimeoutError(f"请求超时，未找到响应（request_id: {request_id}）")

    async def get_send_msg_to_napcat(self):
        """循环从Bot中取出消息交给其他方法处理"""
        while True:
            try:
                # 区分使用哪种发送方式处理payload
                init_payload: dict = await asyncio.wait_for(
                    self.send_msg_queue.get(), timeout=1.0
                )
                self.send_msg_queue.task_done()
                send_result = None  # 存储发送结果，最终回传给bot
                if init_payload["send_type"] == "websocket":
                    payload = init_payload["payload"]
                    send_result = await self.websocket_send(payload)
                elif init_payload["send_type"] == "http":
                    payload = init_payload["payload"]
                    send_result = await self.http_send(payload)
                else:
                    self.log.warning(f"未知的send_type类型：{init_payload['send_type']}")
                    send_result = {"status": "error", "message": f"未知的send_type: {init_payload['send_type']}"}

                # 将发送结果回传给bot（核心补充：确保bot能收到响应）
                if send_result is not None:
                    # 补充关联原消息的标识（方便bot匹配）
                    send_result["request_echo"] = payload.get("echo", "")
                    await self.send_response_queue.put(send_result)

            except asyncio.TimeoutError:
                continue  # 超时继续，检测是否需要退出
            except asyncio.CancelledError:
                self.log.info("发送消息循环收到取消信号，退出")
                break
            except Exception as e:
                self.log.error(f"处理发送队列消息错误: {e}")
                # 异常场景也向bot回传错误信息
                error_result = {"status": "error", "message": f"处理消息失败: {str(e)}"}
                await self.send_response_queue.put(error_result)

    async def websocket_send(self, payload: dict) -> dict:
        """通过websocket向napcat发送消息，返回发送结果"""
        try:
            request_uuid = payload.get("echo","")
            # 检查空id
            if not request_uuid:
                return {}
            # 检查活跃连接
            if not self.active_connections:
                raise RuntimeError("无可用的websocket活跃连接")

            conn = next(iter(self.active_connections))
            await conn.send(json.dumps(payload, ensure_ascii=False))
            # 获取消息响应
            response = await self.get_response(request_uuid)
            if response.get("status") == "ok":
                self.log.info(f"Websocket消息发送成功（request_id: {request_uuid}）")
            else:
                self.log.warning(f"Websocket消息发送失败（request_id: {request_uuid}），napcat返回：{str(response)}")
            return response

        except TimeoutError as e:
            self.log.error(f"Websocket发送消息超时（request_id: {request_uuid}）：{e}")
            return {"status": "error", "message": "timeout", "echo": request_uuid}
        except Exception as e:
            self.log.error(f"Websocket发送消息错误（request_id: {request_uuid}）：{e}")
            return {"status": "error", "message": str(e), "echo": request_uuid}

    async def http_send(self, payload: dict) -> dict:
        """通过HTTP向napcat发送消息，返回发送结果"""
        # 定义超时时间，避免无限等待
        timeout = aiohttp.ClientTimeout(total=60)
        try:
            # 提取action并拼接URL
            action = payload.pop("action")
            url = f"http://{self.http_server_ip}:{self.http_server_port}/{action}"

            # 异步发送POST请求
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(url=url, json=payload) as response:
                    res_data = await response.json()

                    if res_data.get("status") == "ok":
                        self.log.info(f"HTTP消息发送成功（action: {action}）")
                    else:
                        self.log.warning(
                            f"HTTP消息发送失败（action: {action}），napcat返回：{json.dumps(res_data, ensure_ascii=False)[:300]}......")
                    return res_data

        except asyncio.TimeoutError:
            self.log.error(f"HTTP发送消息超时（action: {action}）")
            return {"status": "error", "message": "timeout", "action": action}
        except aiohttp.ClientError as e:
            self.log.error(f"异步HTTP请求异常（action: {action}）：{str(e)}")
            return {"status": "error", "message": f"aiohttp error: {str(e)}", "action": action}
        except ValueError as e:
            self.log.error(f"响应体JSON解析失败（action: {action}）：{str(e)}"[:1000])
            return {"status": "error", "message": "json parse error", "action": action}
        except Exception as e:
            self.log.error(f"HTTP发送消息未知错误（action: {action}）：{str(e)}")
            return {"status": "error", "message": f"unknown error: {str(e)}", "action": action}

    async def message_recv(self, server_connection: Server.ServerConnection):
        """接收napcat的websocket消息，分发到对应队列"""
        self.active_connections.add(server_connection)
        try:
            async for raw_message in server_connection:
                # 日志截断过长消息
                log_msg = raw_message[:100] + "..." if len(raw_message) > 100 else raw_message
                self.log.info(f"收到napcat消息：{log_msg}")

                decoded_raw_message: dict = json.loads(raw_message)
                post_type = decoded_raw_message.get("post_type")

                # 普通消息：转发给bot
                if post_type in ["message"]:
                    await self.message_queue.put(decoded_raw_message)
                # 响应类消息：存入临时队列供get_response匹配
                elif post_type is None:
                    await self.put_response(decoded_raw_message)
        except json.JSONDecodeError as e:
            self.log.error(f"消息JSON解析失败：{e}，原始消息：{raw_message[:200]}")
        finally:
            self.active_connections.discard(server_connection)

    async def start_server(self):
        """启动Adapter服务（websocket服务+消息发送循环）"""
        try:
            self.log.info("正在启动adapter...")
            # 启动websocket服务
            async with Server.serve(self.message_recv, host=self.host, port=self.port) as self.server:
                self.log.info(f"Adapter已启动，监听地址: ws://{self.host}:{self.port}")
                # 启动消息发送循环任务
                send_task = asyncio.create_task(self.get_send_msg_to_napcat())
                # 等待websocket服务和发送任务结束
                await asyncio.gather(self.server.serve_forever(), send_task)
        except asyncio.CancelledError:
            self.log.info("Adapter服务收到取消信号，正在关闭")
            if self.server:
                self.server.close()
                await self.server.wait_closed()
        finally:
            self.log.info("Adapter服务已关闭")