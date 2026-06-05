import json
import os
import configparser
from k3cloud_webapi_sdk.main import K3CloudApiSdk
from core.config import settings


def _extract_erp_error(response_data):
    candidates = []
    if isinstance(response_data, dict):
        candidates.append(response_data)
    elif isinstance(response_data, list) and response_data:
        first = response_data[0]
        if isinstance(first, dict):
            candidates.append(first)
        elif isinstance(first, list) and first and isinstance(first[0], dict):
            candidates.append(first[0])

    for candidate in candidates:
        result = candidate.get("Result")
        if not isinstance(result, dict):
            continue

        response_status = result.get("ResponseStatus")
        if not isinstance(response_status, dict):
            continue
        if response_status.get("IsSuccess") is True:
            continue

        errors = response_status.get("Errors") or []
        messages = []
        for error in errors:
            if isinstance(error, dict):
                message = error.get("Message") or error.get("FieldName") or error.get("DIndex")
                if message:
                    messages.append(str(message))

        message = response_status.get("Message") or response_status.get("MsgCode") or result.get("Message")
        if message:
            messages.insert(0, str(message))

        return "；".join(dict.fromkeys(messages)) or "ERP 返回错误响应"

    return None

class KingdeeClient:
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(KingdeeClient, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
            
        # 定位配置文件
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = str(settings.KINGDEE_CONFIG_PATH or os.path.join(self.base_dir, "conf.ini"))
        
        if not os.path.exists(self.config_path):
            print(f"Warning: Configuration file not found at {self.config_path}")
            self.config = {}
        else:
            self.config = self._read_config()
        
        self.server_url = self.config.get('X-KDApi-ServerUrl', "http://erp.julan.com.cn:8081/k3cloud/")
        if not self.server_url.endswith('/'):
            self.server_url += '/'
            
        # 初始化 SDK
        self.sdk = K3CloudApiSdk(self.server_url)
        
        # 如果配置文件存在，尝试初始化 SDK 配置
        if os.path.exists(self.config_path):
            try:
                # 注意：Init 方法通常返回 True/False，或者抛出异常
                self.sdk.Init(config_path=self.config_path, config_node="config")
                print("K3Cloud SDK initialized successfully.")
            except Exception as e:
                print(f"Failed to initialize K3Cloud SDK: {e}")

        self._initialized = True

    def _read_config(self):
        """读取 conf.ini 中的配置 (辅助方法，主要用于调试或备用)"""
        cf = configparser.ConfigParser()
        try:
            cf.read(self.config_path, encoding='utf-8')
        except Exception:
            cf.read(self.config_path)
            
        config = {}
        if 'config' in cf.sections():
            for key, value in cf.items('config'):
                config[key] = value
                
        # 再次尝试手动解析以获取正确的大小写 Key
        raw_config = {}
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith(';'):
                        continue
                    if '=' in line:
                        parts = line.split('=', 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        raw_config[key] = value
        
        return {**config, **raw_config}

    def _execute_query_once(self, para):
        response_str = self.sdk.ExecuteBillQuery(para)
        response_data = json.loads(response_str)
        erp_error = _extract_erp_error(response_data)
        if erp_error:
            raise RuntimeError(erp_error)
        return response_data

    def execute_query(self, para):
        """执行单据查询"""
        try:
            try:
                return self._execute_query_once(para)
            except (json.JSONDecodeError, RuntimeError) as first_error:
                print(f"ERP query failed, retrying with re-initialization: {first_error}")
                self.sdk.Init(config_path=self.config_path, config_node="config")
                return self._execute_query_once(para)

        except Exception as e:
            print(f"Execute query failed: {e}")
            raise e

# 全局单例
client = KingdeeClient()
