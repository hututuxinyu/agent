"""房源API客户端"""
import httpx
from typing import Dict, Any, Optional, List
from config import HOUSE_API_BASE_URL, REQUEST_TIMEOUT


class HouseAPIClient:
    """房源API客户端，封装所有房源相关API调用"""
    
    def __init__(self, user_id: str):
        """
        初始化客户端
        
        Args:
            user_id: 用户ID，用于X-User-ID请求头
        """
        self.user_id = user_id
        self.base_url = HOUSE_API_BASE_URL
        self.headers = {
            "X-User-ID": user_id,
            "Content-Type": "application/json"
        }
        self.timeout = REQUEST_TIMEOUT
    
    async def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        need_user_id: bool = True
    ) -> Dict[str, Any]:
        """
        发送HTTP请求
        
        Args:
            method: HTTP方法
            endpoint: API端点
            params: 查询参数
            json_data: JSON请求体
            need_user_id: 是否需要X-User-ID请求头
        
        Returns:
            API响应数据
        """
        url = f"{self.base_url}{endpoint}"
        headers = self.headers if need_user_id else {"Content-Type": "application/json"}
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                json=json_data
            )
            response.raise_for_status()
            return response.json()
    
    async def init_houses(self) -> Dict[str, Any]:
        """重置房源数据"""
        return await self._request("POST", "/api/houses/init")
    
    # 地标相关接口（不需要X-User-ID）
    
    async def get_landmarks(
        self,
        category: Optional[str] = None,
        district: Optional[str] = None
    ) -> Dict[str, Any]:
        """获取地标列表"""
        params = {}
        if category:
            params["category"] = category
        if district:
            params["district"] = district
        return await self._request("GET", "/api/landmarks", params=params, need_user_id=False)
    
    async def get_landmark_by_name(self, name: str) -> Dict[str, Any]:
        """按名称精确查询地标"""
        return await self._request("GET", f"/api/landmarks/name/{name}", need_user_id=False)
    
    async def search_landmarks(
        self,
        q: str,
        category: Optional[str] = None,
        district: Optional[str] = None
    ) -> Dict[str, Any]:
        """关键词模糊搜索地标"""
        params = {"q": q}
        if category:
            params["category"] = category
        if district:
            params["district"] = district
        return await self._request("GET", "/api/landmarks/search", params=params, need_user_id=False)
    
    async def get_landmark_by_id(self, landmark_id: str) -> Dict[str, Any]:
        """按地标ID查询地标详情"""
        return await self._request("GET", f"/api/landmarks/{landmark_id}", need_user_id=False)
    
    async def get_landmark_stats(self) -> Dict[str, Any]:
        """获取地标统计信息"""
        return await self._request("GET", "/api/landmarks/stats", need_user_id=False)
    
    # 房源相关接口（需要X-User-ID）
    
    async def get_house_by_id(self, house_id: str) -> Dict[str, Any]:
        """根据房源ID获取详情"""
        return await self._request("GET", f"/api/houses/{house_id}")
    
    async def get_house_listings(self, house_id: str) -> Dict[str, Any]:
        """根据房源ID获取各平台挂牌记录"""
        return await self._request("GET", f"/api/houses/listings/{house_id}")
    
    async def get_houses_by_community(
        self,
        community: str,
        listing_platform: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """按小区名查询可租房源"""
        params = {"community": community}
        if listing_platform:
            params["listing_platform"] = listing_platform
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size
        return await self._request("GET", "/api/houses/by_community", params=params)
    
    async def get_houses_by_platform(
        self,
        listing_platform: Optional[str] = None,
        district: Optional[str] = None,
        area: Optional[str] = None,
        min_price: Optional[int] = None,
        max_price: Optional[int] = None,
        bedrooms: Optional[str] = None,
        rental_type: Optional[str] = None,
        decoration: Optional[str] = None,
        orientation: Optional[str] = None,
        elevator: Optional[str] = None,
        min_area: Optional[int] = None,
        max_area: Optional[int] = None,
        property_type: Optional[str] = None,
        subway_line: Optional[str] = None,
        max_subway_dist: Optional[int] = None,
        subway_station: Optional[str] = None,
        utilities_type: Optional[str] = None,
        available_from_before: Optional[str] = None,
        commute_to_xierqi_max: Optional[int] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """按挂牌平台筛选房源（支持多条件筛选）"""
        params = {}
        if listing_platform:
            params["listing_platform"] = listing_platform
        if district:
            params["district"] = district
        if area:
            params["area"] = area
        if min_price is not None:
            params["min_price"] = min_price
        if max_price is not None:
            params["max_price"] = max_price
        if bedrooms:
            params["bedrooms"] = bedrooms
        if rental_type:
            params["rental_type"] = rental_type
        if decoration:
            params["decoration"] = decoration
        if orientation:
            params["orientation"] = orientation
        if elevator:
            params["elevator"] = elevator
        if min_area is not None:
            params["min_area"] = min_area
        if max_area is not None:
            params["max_area"] = max_area
        if property_type:
            params["property_type"] = property_type
        if subway_line:
            params["subway_line"] = subway_line
        if max_subway_dist is not None:
            params["max_subway_dist"] = max_subway_dist
        if subway_station:
            params["subway_station"] = subway_station
        if utilities_type:
            params["utilities_type"] = utilities_type
        if available_from_before:
            params["available_from_before"] = available_from_before
        if commute_to_xierqi_max is not None:
            params["commute_to_xierqi_max"] = commute_to_xierqi_max
        if sort_by:
            params["sort_by"] = sort_by
        if sort_order:
            params["sort_order"] = sort_order
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size
        
        return await self._request("GET", "/api/houses/by_platform", params=params)
    
    async def get_houses_nearby(
        self,
        landmark_id: str,
        max_distance: Optional[float] = None,
        listing_platform: Optional[str] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """以地标为圆心查附近房源"""
        params = {"landmark_id": landmark_id}
        if max_distance is not None:
            params["max_distance"] = max_distance
        if listing_platform:
            params["listing_platform"] = listing_platform
        if page:
            params["page"] = page
        if page_size:
            params["page_size"] = page_size
        return await self._request("GET", "/api/houses/nearby", params=params)
    
    async def get_nearby_landmarks(
        self,
        community: str,
        type: Optional[str] = None,
        max_distance_m: Optional[float] = None
    ) -> Dict[str, Any]:
        """查询小区周边地标"""
        params = {"community": community}
        if type:
            params["type"] = type
        if max_distance_m is not None:
            params["max_distance_m"] = max_distance_m
        return await self._request("GET", "/api/houses/nearby_landmarks", params=params)
    
    async def get_house_stats(self) -> Dict[str, Any]:
        """获取房源统计信息"""
        return await self._request("GET", "/api/houses/stats")
    
    async def rent_house(self, house_id: str, listing_platform: str) -> Dict[str, Any]:
        """租房操作"""
        params = {"listing_platform": listing_platform}
        return await self._request("POST", f"/api/houses/{house_id}/rent", params=params)
    
    async def terminate_rent(self, house_id: str, listing_platform: str) -> Dict[str, Any]:
        """退租操作"""
        params = {"listing_platform": listing_platform}
        return await self._request("POST", f"/api/houses/{house_id}/terminate", params=params)
    
    async def offline_house(self, house_id: str, listing_platform: str) -> Dict[str, Any]:
        """下架操作"""
        params = {"listing_platform": listing_platform}
        return await self._request("POST", f"/api/houses/{house_id}/offline", params=params)
