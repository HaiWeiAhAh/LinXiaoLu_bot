import asyncio
import json

import aiohttp
from utils.config import ConfigManager

cfg = ConfigManager("test_config.ini")
http_server_ip = cfg.get("http","server_ip")
http_server_port = cfg.get("http","server_port")

async def http_send(payload: dict) -> dict:
    """通过HTTP向napcat发送消息，返回发送结果"""
    # 定义超时时间，避免无限等待
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        # 提取action并拼接URL
        action = payload.pop("action")
        url = f"http://{http_server_ip}:{http_server_port}/{action}"

        # 异步发送POST请求
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url=url, json=payload) as response:
                res_data = await response.json()

                if res_data.get("status") == "ok":
                    print(f"HTTP消息发送成功（action: {action}）")
                else:
                    print(
                        f"HTTP消息发送失败（action: {action}），napcat返回：{json.dumps(res_data, ensure_ascii=False)[:300]}......")
                return res_data

    except asyncio.TimeoutError:
        print(f"HTTP发送消息超时（action: {action}）")
        return {"status": "error", "message": "timeout", "action": action}
    except aiohttp.ClientError as e:
        print(f"异步HTTP请求异常（action: {action}）：{str(e)}")
        return {"status": "error", "message": f"aiohttp error: {str(e)}", "action": action}
    except ValueError as e:
        print(f"响应体JSON解析失败（action: {action}）：{str(e)}"[:1000])
        return {"status": "error", "message": "json parse error", "action": action}
    except Exception as e:
        print(f"HTTP发送消息未知错误（action: {action}）：{str(e)}")
        return {"status": "error", "message": f"unknown error: {str(e)}", "action": action}

if __name__ == "__main__":
    while True:
        print("--------------------tset-----------------------")
        initial_payload = {
            "action": str,
        }
        #构建payload
        action = input("选择action:1.send_group_msg 2.send_private_msg 3.send_poke 4.输入完整的字符串payload/其他类型")
        if action == "send_group_msg" or action == 1:
            initial_payload["action"] = "send_group_msg"
            initial_payload["group_id"] = None
            initial_payload["message"] = []
        elif action == "send_private_msg" or action == 2:
            initial_payload["action"] = "send_private_msg"
            initial_payload["user_id"] = None
            initial_payload["message"] = []
        elif action == "send_poke" or action == 3:
            initial_payload["action"] = "send_poke"
            initial_payload["user_id"] = None
            initial_payload["group_id"] = None
        elif action == "send_poke" or action == 4:
            init_payload = input("请输入完整的payload")
            payload = json.loads(init_payload)
            print(f"原输入payload为：{str(payload)}")
            response = http_send(payload=payload)
            print(f"消息响应为：{response}")
            continue
        else:
            initial_payload["action"] = input("请输入自定义action")
        #输入其他的必要参数
        while True:
            key = input("输入必要键:")
            value = input("输入对应的值：")
            initial_payload[key] = value
            is_counit = input("是否下一步 1.继续输入 2.下一步")
            if is_counit == 1:
                continue
            else:
                break
        #发送payload/http
        message = []
        while True:
            msg_type = input("请输入消息类型：")
            input_data = input("请输入消息数据（json）格式")
            data = json.loads(input_data)
            msg = {"type": msg_type, "data": data}
            message.append(msg)
            next_inout = input("是否下一步 1.继续输入消息 2.下一步")
            if next_inout == "1":
                continue
            elif next_inout == "2":
                break

        response = http_send(payload=payload)

        print(f"消息响应:{response}")
