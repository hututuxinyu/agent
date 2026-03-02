import requests
import json

def call_llm_api():
    """
    同步调用LLM接口
    请求URL: http://7.225.29.223:8888/v2/chat/completions
    """
    # 接口地址
    url = "http://7.225.29.223:8888/v2/chat/completions"
    
    # 完整请求体（和你提供的完全一致）
    payload = {
        "model": "",
        "messages": [
            {
                "role": "user",
                "content": "大兴两居，租金包水电费的房源有吗？"
            },
            {
                "role": "user",
                "content": "3500 以内有没有？"
            }
        ],
        "stream": False,
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "search_houses",
                    "description": "查询可租房源，支持多条件筛选（行政区、商圈、价格、户型、面积、地铁距离等）",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "district": {"type": "string", "description": "行政区，如 海淀、朝阳，多个用逗号分隔"},
                            "area": {"type": "string", "description": "商圈，如 西二旗、上地，多个用逗号分隔"},
                            "min_price": {"type": "integer", "description": "最低月租金（元）"},
                            "max_price": {"type": "integer", "description": "最高月租金（元）"},
                            "bedrooms": {"type": "string", "description": "卧室数，如 1,2 表示一居或两居"},
                            "rental_type": {"type": "string", "description": "整租 或 合租"},
                            "decoration": {"type": "string", "description": "装修类型，如 精装、简装"},
                            "orientation": {"type": "string", "description": "朝向，如 朝南、南北"},
                            "elevator": {"type": "string", "description": "是否有电梯：true/false"},
                            "min_area": {"type": "integer", "description": "最小面积（平米）"},
                            "max_area": {"type": "integer", "description": "最大面积（平米）"},
                            "subway_line": {"type": "string", "description": "地铁线路，如 13号线"},
                            "subway_station": {"type": "string", "description": "地铁站名，如 车公庄站"},
                            "max_subway_dist": {"type": "integer", "description": "最大地铁距离（米），近地铁建议800"},
                            "commute_to_xierqi_max": {"type": "integer", "description": "到西二旗通勤时间上限（分钟）"},
                            "sort_by": {"type": "string", "description": "排序字段：price/area/subway"},
                            "sort_order": {"type": "string", "description": "排序顺序：asc/desc"},
                            "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"},
                            "page": {"type": "integer", "description": "页码，默认1"},
                            "page_size": {"type": "integer", "description": "每页条数，默认10，最大10000"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_house_detail",
                    "description": "根据房源ID获取房源详情",
                    "parameters": {
                        "type": "object",
                        "properties": {"house_id": {"type": "string", "description": "房源ID，如 HF_2001"}},
                        "required": ["house_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_landmarks",
                    "description": "搜索地标（地铁站、公司、商圈等），支持关键词模糊搜索",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string", "description": "搜索关键词，如 西二旗、百度"},
                            "category": {"type": "string", "description": "地标类别：subway(地铁)/company(公司)/landmark(商圈)"},
                            "district": {"type": "string", "description": "行政区，如 海淀、朝阳"}
                        },
                        "required": ["q"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_nearby_houses",
                    "description": "以地标为圆心，查询在指定距离内的可租房源",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "landmark_id": {"type": "string", "description": "地标ID或地标名称"},
                            "max_distance": {"type": "number", "description": "最大直线距离（米），默认2000"},
                            "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"},
                            "page": {"type": "integer", "description": "页码，默认1"},
                            "page_size": {"type": "integer", "description": "每页条数，默认10"}
                        },
                        "required": ["landmark_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rent_house",
                    "description": "租房操作，将房源设为已租状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "house_id": {"type": "string", "description": "房源ID，如 HF_2001"},
                            "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"}
                        },
                        "required": ["house_id", "listing_platform"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "terminate_rent",
                    "description": "退租操作，将房源恢复为可租状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "house_id": {"type": "string", "description": "房源ID，如 HF_2001"},
                            "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"}
                        },
                        "required": ["house_id", "listing_platform"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "offline_house",
                    "description": "下架操作，将房源设为下架状态",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "house_id": {"type": "string", "description": "房源ID，如 HF_2001"},
                            "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"}
                        },
                        "required": ["house_id", "listing_platform"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_house_stats",
                    "description": "获取房源统计信息（总套数、按状态/行政区/户型分布、价格区间等）",
                    "parameters": {"type": "object", "properties": {}}
                }
            }
        ]
    }
    
    # 请求头（模拟Postman/curl行为）
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Python-requests/2.31.0",
        "Connection": "close"  # 避免长连接问题
    }
    
    # 打印请求信息（方便调试）
    print("=" * 80)
    print("【请求信息】")
    print(f"URL: {url}")
    print(f"Headers: {json.dumps(headers, ensure_ascii=False, indent=2)}")
    print(f"Payload长度: {len(json.dumps(payload))} 字符")
    print("=" * 80)
    
    try:
        # 发送POST请求（设置60秒超时，解决5.4 gateway核心问题）
        response = requests.post(
            url=url,
            headers=headers,
            json=payload,  # 自动序列化并处理特殊字符
            timeout=60.0   # 核心：设置合理超时，而非无限等待
        )
        
        # 打印响应信息
        print("=" * 80)
        print("【响应信息】")
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print(f"响应内容（前1000字符）: {response.text[:1000]}...")
        if len(response.text) > 1000:
            print(f"... (总长度: {len(response.text)} 字符)")
        print("=" * 80)
        
        # 检查状态码
        response.raise_for_status()
        
        # 解析响应结果
        result = response.json()
        print("【调用成功】最终响应结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        
        return result
        
    except requests.exceptions.HTTPError as e:
        # HTTP状态码错误（如5.4 gateway）
        error_msg = f"HTTP错误 - 状态码: {response.status_code}, 内容: {response.text}"
        print(f"\n❌ 调用失败: {error_msg}")
        raise Exception(error_msg)
    
    except requests.exceptions.Timeout:
        error_msg = "请求超时（60秒），请检查接口是否正常或网络是否通畅"
        print(f"\n❌ 调用失败: {error_msg}")
        raise Exception(error_msg)
    
    except requests.exceptions.ConnectionError:
        error_msg = "连接失败，请检查IP/端口是否可达，或防火墙是否放行"
        print(f"\n❌ 调用失败: {error_msg}")
        raise Exception(error_msg)
    
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        print(f"\n❌ 调用失败: {error_msg}")
        raise Exception(error_msg)

if __name__ == "__main__":
    # 执行调用
    try:
        call_llm_api()
    except Exception as e:
        print(f"\n脚本执行失败: {e}")