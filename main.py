import asyncio
import sys

from src.bot import Bot
from utils.config import ConfigManager
from utils.logger import LoggerManager
from src.napcat_adapter import Adapter

global_message_queue = asyncio.Queue()
global_send_message_queue = asyncio.Queue()

async def start_adapter(cfg,log):
    """模拟Adapter：无限循环运行，捕获取消信号优雅退出"""
    log = log.get_logger("adapter")
    log.info("Adapter 启动成功，开始监听消息...")
    adapter = Adapter(cfg=cfg, log=log,global_message_queue=global_message_queue,global_send_queue=global_send_message_queue)
    #模拟你的Adapter核心逻辑（比如WebSocket监听）
    server_task = asyncio.create_task(adapter.start_server())
    send_msg_task = asyncio.create_task(adapter.get_send_msg_to_napcat())
    try:
        await asyncio.gather(server_task,send_msg_task)
    except asyncio.CancelledError:
        # 关键：捕获取消信号，执行资源清理（根据你的业务补充）
        server_task.cancel()
        send_msg_task.cancel()
        log.info("Adapter：收到退出信号，正在清理资源（关闭WebSocket/队列）...")
    finally:
        log.info("Adapter：已优雅退出")
async def start_bot(cfg, log):
    """模拟Bot：无限循环运行，捕获取消信号优雅退出"""
    log = log.get_logger("bot")
    log.info("Bot 启动成功，开始处理消息...")
    bot = Bot(log=log, message_queue=global_message_queue,send_message_queue =global_send_message_queue )
    try:
        await bot.run()
    except asyncio.CancelledError:
        # 关键：捕获取消信号，执行资源清理
        log.info("Bot：收到退出信号，正在清理资源（保存未处理消息）...")
    finally:
        log.info("Bot：已优雅退出")
async def main(log):
    global_cfg = ConfigManager("config.ini")
    global_logger = log
    #并发启动任务
    _ = await asyncio.gather(start_bot(cfg=global_cfg,log=global_logger), start_adapter(cfg=global_cfg,log=global_logger))
async def graceful_shutdown():
    try:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 15)
    except Exception as e:
        logger.error(f"Adapter关闭中出现错误: {e}")


if __name__ == "__main__":
    logger_mgr = LoggerManager("config.ini")
    logger = logger_mgr.logger
    logger.info("程序开始启动...")
    # 显式创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 并行启动adapter和bot（核心：两个任务同时运行）
        loop.run_until_complete(main(log=logger_mgr))
    except KeyboardInterrupt:
        # 按下Ctrl+C触发优雅关闭
        logger.warning("收到中断信号，正在优雅关闭...")
        loop.run_until_complete(graceful_shutdown())
    except Exception as e:
        logger.exception(f"主程序异常: {str(e)}")
        sys.exit(1)
    finally:
        if loop and not loop.is_closed():
            loop.close()
        sys.exit(0)