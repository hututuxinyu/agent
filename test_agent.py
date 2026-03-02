"""Agent测试脚本"""
import asyncio
import json
import httpx
from typing import Dict, Any


async def test_chat(model_ip: str, session_id: str, message: str) -> Dict[str, Any]:
    """
    测试聊天接口
    
    Args:
        model_ip: 模型IP
        session_id: 会话ID
        message: 用户消息
    
    Returns:
        响应结果
    """
    url = "http://localhost:8191/api/v1/chat"
    payload = {
        "model_ip": model_ip,
        "session_id": session_id,
        "message": message
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        return response.json()


async def test_case_1():
    """测试用例1: 东城区精装两居，租金5000以内，离地铁500米以内"""
    print("\n=== 测试用例1 ===")
    result = await test_chat(
        model_ip="127.0.0.1",  # 需要替换为实际的模型IP
        session_id="EV-43",
        message="东城区精装两居，租金 5000 以内，离地铁 500 米以内的有吗？"
    )
    print(f"响应: {json.dumps(result, ensure_ascii=False, indent=2)}")
    return result


async def test_case_2():
    """测试用例2: 西城区离地铁近的一居室"""
    print("\n=== 测试用例2 - 第一轮 ===")
    result1 = await test_chat(
        model_ip="127.0.0.1",  # 需要替换为实际的模型IP
        session_id="EV-46",
        message="西城区离地铁近的一居室有吗？按离地铁从近到远排。"
    )
    print(f"响应: {json.dumps(result1, ensure_ascii=False, indent=2)}")
    
    print("\n=== 测试用例2 - 第二轮 ===")
    result2 = await test_chat(
        model_ip="127.0.0.1",  # 需要替换为实际的模型IP
        session_id="EV-46",
        message="还有其他的吗？把所有符合条件的都给出来"
    )
    print(f"响应: {json.dumps(result2, ensure_ascii=False, indent=2)}")
    return result1, result2


async def test_case_3():
    """测试用例3: 海淀区离地铁近的两居"""
    print("\n=== 测试用例3 - 第一轮 ===")
    result1 = await test_chat(
        model_ip="127.0.0.1",  # 需要替换为实际的模型IP
        session_id="EV-45",
        message="海淀区离地铁近的两居有吗？按离地铁从近到远排一下。"
    )
    print(f"响应: {json.dumps(result1, ensure_ascii=False, indent=2)}")
    
    print("\n=== 测试用例3 - 第二轮 ===")
    result2 = await test_chat(
        model_ip="127.0.0.1",  # 需要替换为实际的模型IP
        session_id="EV-45",
        message="就租最近的那套吧。"
    )
    print(f"响应: {json.dumps(result2, ensure_ascii=False, indent=2)}")
    return result1, result2


async def main():
    """主测试函数"""
    print("开始测试租房AI Agent...")
    print("注意: 请确保Agent服务已启动（python main.py）")
    print("注意: 请将model_ip替换为实际的模型IP地址")
    
    try:
        # 测试用例1
        await test_case_1()
        
        # 测试用例2
        await test_case_2()
        
        # 测试用例3
        await test_case_3()
        
        print("\n所有测试完成！")
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
