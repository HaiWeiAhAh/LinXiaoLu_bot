import asyncio
import json
import aiohttp
from config import ConfigManager

cfg = ConfigManager("test_config.ini")
http_server_ip = cfg.get("http", "server_ip")
http_server_port = cfg.get("http", "server_port")


async def http_send(payload: dict) -> dict:
    """通过HTTP向napcat发送消息，返回发送结果"""
    # 定义超时时间，避免无限等待
    timeout = aiohttp.ClientTimeout(total=60)
    try:
        # 提取action并拼接URL（先复制payload，避免修改原字典）
        action = payload.get("action")
        if not action:
            print("payload中缺少必要的action字段")
            return {"status": "error", "message": "missing action"}

        # 拼接完整URL（napcat的HTTP接口通常是 /api/{action}，根据实际调整）
        url = f"http://{http_server_ip}:{http_server_port}/api/{action}"

        # 异步发送POST请求
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url=url, json=payload) as response:
                # 先获取响应文本，方便排查错误
                res_text = await response.text()
                try:
                    res_data = json.loads(res_text)
                except json.JSONDecodeError:
                    print(f"响应不是合法JSON，原始内容：{res_text[:500]}")
                    return {"status": "error", "message": "response not json", "raw": res_text[:500]}

                if res_data.get("status") == "ok":
                    print(f"✅ HTTP消息发送成功（action: {action}）")
                else:
                    print(
                        f"❌ HTTP消息发送失败（action: {action}），napcat返回：{json.dumps(res_data, ensure_ascii=False)[:300]}......")
                return res_data

    except asyncio.TimeoutError:
        print(f"⏰ HTTP发送消息超时（action: {action}）")
        return {"status": "error", "message": "timeout", "action": action}
    except aiohttp.ClientError as e:
        print(f"🔌 异步HTTP请求异常（action: {action}）：{str(e)}")
        return {"status": "error", "message": f"aiohttp error: {str(e)}", "action": action}
    except Exception as e:
        print(f"❓ HTTP发送消息未知错误（action: {action}）：{str(e)}")
        return {"status": "error", "message": f"unknown error: {str(e)}", "action": action}


async def main():
    """主交互逻辑（异步）"""
    print("===== Napcat HTTP 消息发送工具 =====")
    print("输入 'exit' 可随时退出程序\n")

    while True:
        print("--------------------test-----------------------")
        initial_payload = {}  # 初始化空字典，避免初始值错误

        # 选择action
        action_input = input(
            "选择action:\n1.send_group_msg 2.send_private_msg 3.send_poke 4.输入完整的字符串payload/其他类型\n请输入序号：")
        # 退出机制
        if action_input.strip().lower() == "exit":
            print("程序退出中...")
            break

        try:
            a = int(action_input)
        except ValueError:
            print("输入无效，请输入数字序号！")
            continue

        # 构建基础payload
        if a == 1:
            initial_payload["action"] = "send_group_msg"
            initial_payload["group_id"] = None  # 后续填充
            initial_payload["message"] = []
        elif a == 2:
            initial_payload["action"] = "send_private_msg"
            initial_payload["user_id"] = None  # 后续填充
            initial_payload["message"] = []
        elif a == 3:
            initial_payload["action"] = "send_poke"
            initial_payload["user_id"] = None  # 后续填充
            initial_payload["group_id"] = None  # 后续填充
        elif a == 4:
            init_payload = input("请输入完整的payload（JSON格式）：")
            # 处理用户输入的完整payload
            try:
                payload = json.loads(init_payload.strip())
            except json.JSONDecodeError as e:
                print(f"JSON解析失败：{e}，请检查格式！")
                continue
            print(f"原输入payload为：{json.dumps(payload, ensure_ascii=False, indent=2)}")
            # 异步调用并等待结果
            response = await http_send(payload=payload)
            print(f"消息响应为：{json.dumps(response, ensure_ascii=False, indent=2)}")
            continue
        else:
            custom_action = input("请输入自定义action：")
            initial_payload["action"] = custom_action

        # 输入必要参数（修复类型判断+支持多参数输入）
        print("\n--- 输入必要参数（输入 'next' 结束参数输入） ---")
        while True:
            key = input("输入参数名（如group_id/user_id）：").strip()
            if key.lower() == "next":
                break
            if not key:
                print("参数名不能为空！")
                continue

            value = input(f"输入{key}对应的值：").strip()
            # 自动转换数字类型（napcat接口通常要求group_id/user_id为整数）
            try:
                # 尝试转整数
                value = int(value)
            except ValueError:
                # 尝试转浮点数（可选）
                try:
                    value = float(value)
                except ValueError:
                    # 保留字符串
                    pass
            initial_payload[key] = value

        # 构建message（修复JSON解析异常+交互逻辑）
        if "message" in initial_payload:
            print("\n--- 构建message消息体（输入 'next' 结束消息输入） ---")
            message = []
            while True:
                msg_type = input("输入消息类型（如text/image/at）：").strip()
                if msg_type.lower() == "next":
                    break
                if not msg_type:
                    print("消息类型不能为空！")
                    continue

                input_data = input(f"输入{msg_type}类型的消息数据（JSON格式，如{{'text':'你好'}}）：").strip()
                try:
                    data = json.loads(input_data)
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败：{e}，跳过该条消息！")
                    continue

                msg = {"type": msg_type, "data": data}
                message.append(msg)
                print(f"已添加消息：{json.dumps(msg, ensure_ascii=False)}")

            initial_payload["message"] = message

        # 发送payload并等待响应
        print("\n正在发送请求...")
        response = await http_send(payload=initial_payload)
        print(f"\n消息响应：{json.dumps(response, ensure_ascii=False, indent=2)}")
        print("----------------------------------------\n")


if __name__ == "__main__":
    # 运行异步主函数
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错：{e}")