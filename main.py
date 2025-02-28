import os
import time
import json
import asyncio
import httpx
from loguru import logger

# 设定日志文件和存储路径
script_dir = os.getcwd()
valid_links_path = os.path.join(script_dir, "valid_links.txt")
config_file_path = os.path.join(script_dir, "config.json")

# 设置日志记录
logger.add("script_log.txt", format="{time} - {message}", level="INFO")

# 确保文件存在
if not os.path.exists(valid_links_path):
    open(valid_links_path, "w").close()

# **加载配置文件**
def load_config():
    if os.path.exists(config_file_path):
        try:
            with open(config_file_path, "r") as config_file:
                config = json.load(config_file)
                if "last_processed_id" not in config:
                    config["last_processed_id"] = config.get("start_id", 5444619000) - 1
                    save_config(**config)
                return config
        except json.JSONDecodeError:
            logger.error("配置文件格式错误，将重新创建配置文件...")
            return create_default_config()
    else:
        logger.info("配置文件不存在，正在创建配置文件并初始化默认值...")
        return create_default_config()

# **创建默认配置文件**
def create_default_config():
    default_config = {
        "start_id": 5444619000,
        "end_id": 8444649000,
        "step": 1,
        "batch_size": 10000,
        "max_workers": 567,  # 固定值
        "last_processed_id": 5444618999
    }
    save_config(**default_config)
    return default_config

# **保存配置文件**
def save_config(**config):
    with open(config_file_path, "w") as config_file:
        json.dump(config, config_file)
    logger.info(f"配置文件已保存：{config_file_path}")

# **异步检查单个相册**
async def check_album_async(album_id, client):
    url = f"https://www.pailixiang.com/m/album_ia{album_id}.html"
    try:
        response = await client.head(url, timeout=2)
        if response.status_code == 200:
            response = await client.get(url, timeout=5)
            if "相册不存在或已删除" not in response.text:
                return url
    except (httpx.RequestError, httpx.TimeoutError):
        pass
    return None

# **异步处理批次**
async def process_batch_async(batch_start_id, batch_end_id):
    global success_count, failure_count, processed_count, current_start_id, last_processed_id
    batch_valid_links = []
    last_print_time = time.time()  # 记录上次打印时间

    async with httpx.AsyncClient(http2=True) as client:
        album_ids = list(range(batch_start_id, batch_end_id, step))
        results = await asyncio.gather(*[check_album_async(id, client) for id in album_ids])
        for result in results:
            processed_count += 1
            if result:
                batch_valid_links.append(result)
                success_count += 1
            else:
                failure_count += 1

            # 每处理 100 个任务或任务完成时，输出进度
            if processed_count % 100 == 0 or processed_count == total_tasks:
                current_time = time.time()
                elapsed_time = current_time - start_time  # 总运行时间
                time_since_last_print = current_time - last_print_time  # 距离上次打印的时间
                last_print_time = current_time

                # 计算速度（每秒处理的任务数量）
                if time_since_last_print > 0:
                    speed = 100 / time_since_last_print  # 每 100 个任务的速度
                else:
                    speed = 0

                print(
                    f"\n🚀 已运行 {elapsed_time:.2f} 秒 | "
                    f"已处理 {processed_count}/{total_tasks} 个相册 ID | "
                    f"速度: {speed:.2f} 个/秒 | "
                    f"✅ 成功: {success_count} | ❌ 失败: {failure_count}",
                    flush=True
                )

    if batch_valid_links:
        with open(valid_links_path, "a") as file:
            file.write("\n".join(batch_valid_links) + "\n")
        logger.info(f"找到 {len(batch_valid_links)} 个有效相册")

    current_start_id = last_processed_id + 1

# **主函数**
async def main():
    global current_start_id
    logger.info(f"📌 从 ID {current_start_id} 开始处理")
    while current_start_id <= end_id:
        current_end_id = min(current_start_id + batch_size, end_id)
        logger.info(f"📌 处理 ID 范围: {current_start_id} - {current_end_id}")
        await process_batch_async(current_start_id, current_end_id)
        current_start_id = current_end_id

# **运行异步主函数**
if __name__ == "__main__":
    config = load_config()
    start_id = config["start_id"]
    end_id = config["end_id"]
    step = config["step"]
    batch_size = config["batch_size"]
    MAX_WORKERS = config["max_workers"]  # 使用配置文件中的固定值
    last_processed_id = config["last_processed_id"]
    current_start_id = last_processed_id + 1

    # 计算总任务数
    total_tasks = len(range(current_start_id, end_id, step))
    logger.info(f"📌 预计处理 {total_tasks} 个相册 ID")

    success_count = 0
    failure_count = 0
    processed_count = 0
    start_time = time.time()

    asyncio.run(main())

    # 最终统计信息
    total_time = time.time() - start_time
    average_speed = processed_count / total_time if total_time > 0 else 0
    logger.info(f"总运行时间: {total_time:.2f} 秒")
    logger.info(f"总共找到 {success_count} 个有效相册")
    logger.info(f"失败 {failure_count} 个")
    logger.info(f"平均每秒处理 {average_speed:.2f} 个相册 ID")