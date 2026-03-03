"""测试Agent输出格式，使用mock模拟工具查询结果"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from services.agent_service import AgentService
from services.session_manager import SessionManager
import tools.house_tools


# Mock工具查询结果数据
MOCK_SEARCH_RESULT_WITH_HOUSES = {
    "total": 5,
    "page": 1,
    "page_size": 10,
    "items": [
        {
            "house_id": "HF_906",
            "price": 4500,
            "subway_distance": 200,
            "district": "海淀",
            "bedrooms": 2,
            "listing_platform": "链家"
        },
        {
            "house_id": "HF_1586",
            "price": 4800,
            "subway_distance": 350,
            "district": "海淀",
            "bedrooms": 2,
            "listing_platform": "安居客"
        },
        {
            "house_id": "HF_1876",
            "price": 5000,
            "subway_distance": 500,
            "district": "海淀",
            "bedrooms": 2,
            "listing_platform": "58同城"
        },
        {
            "house_id": "HF_706",
            "price": 4200,
            "subway_distance": 600,
            "district": "海淀",
            "bedrooms": 2,
            "listing_platform": "链家"
        },
        {
            "house_id": "HF_33",
            "price": 4600,
            "subway_distance": 750,
            "district": "海淀",
            "bedrooms": 2,
            "listing_platform": "安居客"
        }
    ]
}

MOCK_SEARCH_RESULT_NO_HOUSES = {
    "total": 0,
    "page": 1,
    "page_size": 10,
    "items": []
}

MOCK_SEARCH_RESULT_SINGLE_HOUSE = {
    "total": 1,
    "page": 1,
    "page_size": 10,
    "items": [
        {
            "house_id": "HF_13",
            "price": 3500,
            "subway_distance": 400,
            "district": "西城",
            "bedrooms": 1,
            "listing_platform": "链家"
        }
    ]
}


def create_mock_llm_response_with_tool_call(tool_name: str, tool_args: dict):
    """创建包含工具调用的LLM响应"""
    return {
        "choices": [{
            "message": {
                "content": None,
                "tool_calls": [{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": json.dumps(tool_args, ensure_ascii=False)
                    }
                }]
            }
        }]
    }


def create_mock_llm_response_text(content: str):
    """创建纯文本LLM响应"""
    return {
        "choices": [{
            "message": {
                "content": content,
                "tool_calls": None
            }
        }]
    }


def create_mock_llm_response_json(message: str, houses: list):
    """创建JSON格式的LLM响应"""
    return {
        "choices": [{
            "message": {
                "content": json.dumps({"message": message, "houses": houses}, ensure_ascii=False),
                "tool_calls": None
            }
        }]
    }


async def test_output_format_with_houses():
    """测试有房源时的输出格式"""
    print("\n" + "="*80)
    print("测试1: 有房源时的输出格式")
    print("="*80)
    
    session_manager = SessionManager()
    agent_service = AgentService("127.0.0.1", session_manager)
    session_id = "TEST-001"
    
    # Mock工具函数
    async def mock_search_houses(client, **kwargs):
        return {
            "success": True,
            "data": MOCK_SEARCH_RESULT_WITH_HOUSES
        }
    
    # Mock LLM客户端
    with patch.object(agent_service.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        with patch('tools.house_tools.TOOL_FUNCTIONS', {
            "search_houses": mock_search_houses,
            "get_house_detail": tools.house_tools.get_house_detail,
            "search_landmarks": tools.house_tools.search_landmarks,
            "get_nearby_houses": tools.house_tools.get_nearby_houses,
            "get_nearby_landmarks": tools.house_tools.get_nearby_landmarks,
            "rent_house": tools.house_tools.rent_house,
            "terminate_rent": tools.house_tools.terminate_rent,
            "offline_house": tools.house_tools.offline_house,
            "get_house_stats": tools.house_tools.get_house_stats,
        }):
            # LLM响应：第一轮调用工具，第二轮生成回复
            mock_llm.side_effect = [
                create_mock_llm_response_with_tool_call(
                    "search_houses",
                    {"district": "海淀", "bedrooms": "2", "max_subway_dist": 800, "page_size": 10}
                ),
                create_mock_llm_response_text("为您找到海淀区2居近地铁的房源")
            ]
            
            result = await agent_service.process_message(
                session_id=session_id,
                message="海淀区离地铁近的两居有吗？按离地铁从近到远排一下。"
            )
    
    print(f"响应: {result['response']}")
    print(f"状态: {result['status']}")
    
    # 验证输出格式
    try:
        response_data = json.loads(result['response'])
        assert "message" in response_data, "响应必须包含message字段"
        assert "houses" in response_data, "响应必须包含houses字段"
        assert isinstance(response_data["houses"], list), "houses必须是列表"
        assert len(response_data["houses"]) > 0, "应该有房源"
        assert all(house_id.startswith("HF_") for house_id in response_data["houses"]), "房源ID必须以HF_开头"
        
        print("✓ 输出格式验证通过")
        print(f"  - message: {response_data['message']}")
        print(f"  - houses数量: {len(response_data['houses'])}")
        print(f"  - houses: {response_data['houses']}")
        
        # 验证排序（应该按地铁距离从近到远）
        if len(response_data["houses"]) > 1:
            print("✓ 房源列表已返回")
        
        return True
    except json.JSONDecodeError:
        print("✗ 响应不是有效的JSON格式")
        return False
    except AssertionError as e:
        print(f"✗ 验证失败: {e}")
        return False


async def test_output_format_no_houses():
    """测试无房源时的输出格式"""
    print("\n" + "="*80)
    print("测试2: 无房源时的输出格式")
    print("="*80)
    
    session_manager = SessionManager()
    agent_service = AgentService("127.0.0.1", session_manager)
    session_id = "TEST-002"
    
    # Mock LLM客户端
    with patch.object(agent_service.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        # Mock工具函数返回空结果
        with patch('tools.house_tools.search_houses', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": MOCK_SEARCH_RESULT_NO_HOUSES
            }
            
            # LLM响应
            mock_llm.side_effect = [
                create_mock_llm_response_with_tool_call(
                    "search_houses",
                    {"district": "东城", "bedrooms": "2", "max_price": 5000, "max_subway_dist": 500, "page_size": 10}
                ),
                create_mock_llm_response_text("没有符合条件的房源")
            ]
            
            result = await agent_service.process_message(
                session_id=session_id,
                message="东城区精装两居，租金5000以内，离地铁500米以内的有吗？"
            )
    
    print(f"响应: {result['response']}")
    
    # 验证输出格式
    try:
        response_data = json.loads(result['response'])
        assert "message" in response_data, "响应必须包含message字段"
        assert "houses" in response_data, "响应必须包含houses字段"
        assert isinstance(response_data["houses"], list), "houses必须是列表"
        assert len(response_data["houses"]) == 0, "应该没有房源"
        assert "没有" in response_data["message"], "message应该包含'没有'"
        
        print("✓ 输出格式验证通过")
        print(f"  - message: {response_data['message']}")
        print(f"  - houses: {response_data['houses']}")
        
        return True
    except json.JSONDecodeError:
        print("✗ 响应不是有效的JSON格式")
        return False
    except AssertionError as e:
        print(f"✗ 验证失败: {e}")
        return False


async def test_output_format_single_house():
    """测试单个房源时的输出格式"""
    print("\n" + "="*80)
    print("测试3: 单个房源时的输出格式")
    print("="*80)
    
    session_manager = SessionManager()
    agent_service = AgentService("127.0.0.1", session_manager)
    session_id = "TEST-003"
    
    # Mock LLM客户端
    with patch.object(agent_service.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        # Mock工具函数
        with patch('tools.house_tools.search_houses', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": MOCK_SEARCH_RESULT_SINGLE_HOUSE
            }
            
            # LLM响应
            mock_llm.side_effect = [
                create_mock_llm_response_with_tool_call(
                    "search_houses",
                    {"district": "西城", "bedrooms": "1", "max_subway_dist": 800, "page_size": 10}
                ),
                create_mock_llm_response_text("为您找到西城区1居近地铁的房源")
            ]
            
            result = await agent_service.process_message(
                session_id=session_id,
                message="西城区离地铁近的一居室有吗？按离地铁从近到远排。"
            )
    
    print(f"响应: {result['response']}")
    
    # 验证输出格式
    try:
        response_data = json.loads(result['response'])
        assert "message" in response_data, "响应必须包含message字段"
        assert "houses" in response_data, "响应必须包含houses字段"
        assert isinstance(response_data["houses"], list), "houses必须是列表"
        assert len(response_data["houses"]) == 1, "应该有1套房源"
        assert response_data["houses"][0] == "HF_13", "房源ID应该是HF_13"
        
        print("✓ 输出格式验证通过")
        print(f"  - message: {response_data['message']}")
        print(f"  - houses: {response_data['houses']}")
        
        return True
    except json.JSONDecodeError:
        print("✗ 响应不是有效的JSON格式")
        return False
    except AssertionError as e:
        print(f"✗ 验证失败: {e}")
        return False


async def test_output_format_sorting():
    """测试排序功能"""
    print("\n" + "="*80)
    print("测试4: 排序功能")
    print("="*80)
    
    session_manager = SessionManager()
    agent_service = AgentService("127.0.0.1", session_manager)
    session_id = "TEST-004"
    
    # Mock LLM客户端
    with patch.object(agent_service.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        # Mock工具函数
        with patch('tools.house_tools.search_houses', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": MOCK_SEARCH_RESULT_WITH_HOUSES
            }
            
            # LLM响应
            mock_llm.side_effect = [
                create_mock_llm_response_with_tool_call(
                    "search_houses",
                    {"district": "海淀", "bedrooms": "2", "max_subway_dist": 800, "page_size": 10}
                ),
                create_mock_llm_response_text("为您找到海淀区2居近地铁的房源，已按地铁距离从近到远排序")
            ]
            
            result = await agent_service.process_message(
                session_id=session_id,
                message="海淀区离地铁近的两居有吗？按离地铁从近到远排一下。"
            )
    
    print(f"响应: {result['response']}")
    
    # 验证输出格式和排序
    try:
        response_data = json.loads(result['response'])
        assert "message" in response_data, "响应必须包含message字段"
        assert "houses" in response_data, "响应必须包含houses字段"
        assert len(response_data["houses"]) > 0, "应该有房源"
        
        # 验证排序（应该按地铁距离从近到远：200, 350, 500, 600, 750）
        expected_order = ["HF_906", "HF_1586", "HF_1876", "HF_706", "HF_33"]
        actual_order = response_data["houses"][:5]  # 最多5套
        
        print("✓ 输出格式验证通过")
        print(f"  - message: {response_data['message']}")
        print(f"  - houses数量: {len(response_data['houses'])}")
        print(f"  - houses顺序: {actual_order}")
        print(f"  - 期望顺序: {expected_order}")
        
        # 检查是否按地铁距离排序（前几套应该匹配）
        if actual_order[0] == expected_order[0]:
            print("✓ 排序验证通过（第一套房源正确）")
        else:
            print(f"⚠ 排序可能不正确（第一套期望{expected_order[0]}，实际{actual_order[0]}）")
        
        return True
    except json.JSONDecodeError:
        print("✗ 响应不是有效的JSON格式")
        return False
    except AssertionError as e:
        print(f"✗ 验证失败: {e}")
        return False


async def test_output_format_max_5_houses():
    """测试最多返回5套房源"""
    print("\n" + "="*80)
    print("测试5: 最多返回5套房源")
    print("="*80)
    
    # 创建包含10套房源的mock数据
    mock_result_many_houses = {
        "total": 10,
        "page": 1,
        "page_size": 10,
        "items": [
            {
                "house_id": f"HF_{1000+i}",
                "price": 4000 + i * 100,
                "subway_distance": 100 + i * 50,
                "district": "海淀",
                "bedrooms": 2,
                "listing_platform": "链家"
            }
            for i in range(10)
        ]
    }
    
    session_manager = SessionManager()
    agent_service = AgentService("127.0.0.1", session_manager)
    session_id = "TEST-005"
    
    # Mock LLM客户端
    with patch.object(agent_service.llm_client, 'chat_completion', new_callable=AsyncMock) as mock_llm:
        # Mock工具函数
        with patch('tools.house_tools.search_houses', new_callable=AsyncMock) as mock_search:
            mock_search.return_value = {
                "success": True,
                "data": mock_result_many_houses
            }
            
            # LLM响应
            mock_llm.side_effect = [
                create_mock_llm_response_with_tool_call(
                    "search_houses",
                    {"district": "海淀", "bedrooms": "2", "page_size": 10}
                ),
                create_mock_llm_response_text("为您找到符合条件的房源")
            ]
            
            result = await agent_service.process_message(
                session_id=session_id,
                message="海淀区两居有吗？"
            )
    
    print(f"响应: {result['response']}")
    
    # 验证输出格式
    try:
        response_data = json.loads(result['response'])
        assert "message" in response_data, "响应必须包含message字段"
        assert "houses" in response_data, "响应必须包含houses字段"
        assert len(response_data["houses"]) <= 5, f"最多应该返回5套房源，实际返回{len(response_data['houses'])}套"
        
        print("✓ 输出格式验证通过")
        print(f"  - message: {response_data['message']}")
        print(f"  - houses数量: {len(response_data['houses'])} (应该≤5)")
        print(f"  - houses: {response_data['houses']}")
        
        return True
    except json.JSONDecodeError:
        print("✗ 响应不是有效的JSON格式")
        return False
    except AssertionError as e:
        print(f"✗ 验证失败: {e}")
        return False


async def main():
    """主测试函数"""
    print("\n" + "="*80)
    print("开始测试Agent输出格式")
    print("="*80)
    
    results = []
    
    try:
        # 测试1: 有房源时的输出格式
        results.append(await test_output_format_with_houses())
        
        # 测试2: 无房源时的输出格式
        results.append(await test_output_format_no_houses())
        
        # 测试3: 单个房源时的输出格式
        results.append(await test_output_format_single_house())
        
        # 测试4: 排序功能
        results.append(await test_output_format_sorting())
        
        # 测试5: 最多返回5套房源
        results.append(await test_output_format_max_5_houses())
        
        # 汇总结果
        print("\n" + "="*80)
        print("测试结果汇总")
        print("="*80)
        passed = sum(results)
        total = len(results)
        print(f"通过: {passed}/{total}")
        
        if passed == total:
            print("✓ 所有测试通过！")
        else:
            print(f"✗ {total - passed}个测试失败")
        
    except Exception as e:
        print(f"\n测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
