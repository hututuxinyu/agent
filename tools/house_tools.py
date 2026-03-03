"""房源相关工具函数"""
import json
from typing import Dict, Any, Optional, List
from services.house_api_client import HouseAPIClient


# 工具定义（用于LLM的tools参数）
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "search_houses",
            "description": "查询可租房源，支持多条件筛选。优先使用。无结果时可放宽条件重试。page_size建议5-10。",
            "parameters": {
                "type": "object",
                "properties": {
                    "district": {"type": "string", "description": "行政区，如 海淀、朝阳，多个用逗号分隔"},
                    "area": {"type": "string", "description": "商圈，如 西二旗、上地"},
                    "min_price": {"type": "integer", "description": "最低月租金（元）"},
                    "max_price": {"type": "integer", "description": "最高月租金（元）"},
                    "bedrooms": {"type": "string", "description": "卧室数，如 1,2"},
                    "rental_type": {"type": "string", "description": "整租 或 合租"},
                    "decoration": {"type": "string", "description": "装修类型"},
                    "orientation": {"type": "string", "description": "朝向"},
                    "elevator": {"type": "string", "description": "是否有电梯：true/false"},
                    "min_area": {"type": "integer", "description": "最小面积（平米）"},
                    "max_area": {"type": "integer", "description": "最大面积（平米）"},
                    "subway_line": {"type": "string", "description": "地铁线路"},
                    "subway_station": {"type": "string", "description": "地铁站名"},
                    "max_subway_dist": {"type": "integer", "description": "最大地铁距离（米），近地铁设为800"},
                    "commute_to_xierqi_max": {"type": "integer", "description": "到西二旗通勤时间上限（分钟）"},
                    "sort_by": {"type": "string", "description": "排序：price/area/subway"},
                    "sort_order": {"type": "string", "description": "排序顺序：asc/desc"},
                    "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"},
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页条数，建议5-10"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_house_detail",
            "description": "获取房源详情",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"}
                },
                "required": ["house_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_landmarks",
            "description": "搜索地标（地铁站、公司、商圈等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string", "description": "搜索关键词"},
                    "category": {"type": "string", "description": "类别：subway/company/landmark"},
                    "district": {"type": "string", "description": "行政区"}
                },
                "required": ["q"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_houses",
            "description": "查询地标附近的可租房源。使用前需通过search_landmarks获取地标ID。",
            "parameters": {
                "type": "object",
                "properties": {
                    "landmark_id": {"type": "string", "description": "地标ID"},
                    "max_distance": {"type": "number", "description": "最大距离（米），默认2000"},
                    "listing_platform": {"type": "string", "description": "挂牌平台：链家/安居客/58同城"},
                    "page": {"type": "integer", "description": "页码，默认1"},
                    "page_size": {"type": "integer", "description": "每页条数，建议5-10"}
                },
                "required": ["landmark_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_nearby_landmarks",
            "description": "查询小区周边地标（商超、公园等）",
            "parameters": {
                "type": "object",
                "properties": {
                    "community": {"type": "string", "description": "小区名称"},
                    "type": {"type": "string", "description": "地标类型"},
                    "max_distance_m": {"type": "number", "description": "最大距离（米），默认3000"}
                },
                "required": ["community"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "rent_house",
            "description": "租房操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"},
                    "listing_platform": {"type": "string", "description": "挂牌平台"}
                },
                "required": ["house_id", "listing_platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "terminate_rent",
            "description": "退租操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"},
                    "listing_platform": {"type": "string", "description": "挂牌平台"}
                },
                "required": ["house_id", "listing_platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "offline_house",
            "description": "下架操作",
            "parameters": {
                "type": "object",
                "properties": {
                    "house_id": {"type": "string", "description": "房源ID"},
                    "listing_platform": {"type": "string", "description": "挂牌平台"}
                },
                "required": ["house_id", "listing_platform"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_house_stats",
            "description": "获取房源统计信息",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


async def search_houses(client: HouseAPIClient, **kwargs) -> Dict[str, Any]:
    """房源查询工具函数"""
    try:
        result = await client.get_houses_by_platform(**kwargs)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_house_detail(client: HouseAPIClient, house_id: str) -> Dict[str, Any]:
    """获取房源详情工具函数"""
    try:
        result = await client.get_house_by_id(house_id)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def search_landmarks(client: HouseAPIClient, q: str, category: Optional[str] = None, district: Optional[str] = None) -> Dict[str, Any]:
    """搜索地标工具函数"""
    try:
        result = await client.search_landmarks(q=q, category=category, district=district)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_nearby_houses(client: HouseAPIClient, landmark_id: str, max_distance: Optional[float] = None, listing_platform: Optional[str] = None, page: Optional[int] = None, page_size: Optional[int] = None) -> Dict[str, Any]:
    """地标附近房源工具函数"""
    try:
        result = await client.get_houses_nearby(
            landmark_id=landmark_id,
            max_distance=max_distance,
            listing_platform=listing_platform,
            page=page,
            page_size=page_size
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_nearby_landmarks(client: HouseAPIClient, community: str, type: Optional[str] = None, max_distance_m: Optional[float] = None) -> Dict[str, Any]:
    """查询小区周边地标工具函数"""
    try:
        result = await client.get_nearby_landmarks(
            community=community,
            type=type,
            max_distance_m=max_distance_m
        )
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def rent_house(client: HouseAPIClient, house_id: str, listing_platform: str) -> Dict[str, Any]:
    """租房操作工具函数"""
    try:
        result = await client.rent_house(house_id=house_id, listing_platform=listing_platform)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def terminate_rent(client: HouseAPIClient, house_id: str, listing_platform: str) -> Dict[str, Any]:
    """退租操作工具函数"""
    try:
        result = await client.terminate_rent(house_id=house_id, listing_platform=listing_platform)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def offline_house(client: HouseAPIClient, house_id: str, listing_platform: str) -> Dict[str, Any]:
    """下架操作工具函数"""
    try:
        result = await client.offline_house(house_id=house_id, listing_platform=listing_platform)
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def get_house_stats(client: HouseAPIClient) -> Dict[str, Any]:
    """房源统计工具函数"""
    try:
        result = await client.get_house_stats()
        return {"success": True, "data": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# 工具函数映射
TOOL_FUNCTIONS = {
    "search_houses": search_houses,
    "get_house_detail": get_house_detail,
    "search_landmarks": search_landmarks,
    "get_nearby_houses": get_nearby_houses,
    "rent_house": rent_house,
    "terminate_rent": terminate_rent,
    "offline_house": offline_house,
    "get_house_stats": get_house_stats,
}
