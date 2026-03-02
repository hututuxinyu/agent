"""测试 /api/houses/init 接口"""
import requests
import json


def test_init_houses():
    """测试初始化房源接口"""
    url = "http://7.225.29.223:8080/api/houses/init"
    headers = {
        "X-User-ID": "h00613474",
        "Content-Type": "application/json"
    }
    
    print(f"正在测试接口: {url}")
    print(f"请求头: {json.dumps(headers, indent=2, ensure_ascii=False)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, headers=headers, timeout=10)
        
        print(f"状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print("-" * 50)
        
        if response.status_code == 200:
            print("✓ 请求成功!")
            try:
                result = response.json()
                print(f"响应内容: {json.dumps(result, indent=2, ensure_ascii=False)}")
            except:
                print(f"响应内容: {response.text}")
        else:
            print(f"✗ 请求失败，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
        response.raise_for_status()
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"✗ 请求异常: {str(e)}")
        return False
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("测试 /api/houses/init 接口")
    print("=" * 50)
    success = test_init_houses()
    print("=" * 50)
    if success:
        print("测试通过 ✓")
    else:
        print("测试失败 ✗")
    print("=" * 50)
