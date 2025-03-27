import streamlit as st
import requests
import plotly.graph_objects as go
import logging
import hashlib
from payment_handler import init_stripe, display_subscription_plans, handle_subscription_status
from cache_handler import CacheHandler
import os
from dotenv import load_dotenv
import re  # 用于邮箱格式验证

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 从环境变量获取API配置
API_BASE_URL = os.getenv('API_BASE_URL', 'http://156.225.26.202:5000')

# 初始化Stripe和缓存系统
stripe_config = init_stripe()
cache_handler = CacheHandler()


# 验证邮箱格式的函数
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


# 简单内存用户存储（替代数据库）
if 'users' not in st.session_state:
    st.session_state['users'] = {}


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(email, company_name, password):
    if not is_valid_email(email):
        st.error('邮箱格式不正确，必须是 xxxx@xxxx.com 的形式')
        return False
    if email in st.session_state['users']:
        st.error('该邮箱已注册')
        return False
    st.session_state['users'][email] = {
        'company_name': company_name,
        'password': hash_password(password)
    }
    st.success("注册成功，请用邮箱登录")
    return True


def login_user(email, password):
    if email in st.session_state['users']:
        user = st.session_state['users'][email]
        if user['password'] == hash_password(password):
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = email
            st.session_state['username'] = user['company_name']
            st.session_state['page'] = 'main'
            st.success("登录成功！")
            st.rerun()
            return True
    # 允许默认测试账户
    if email == "hzhbond@hotmail.com" and password == "admin":
        st.session_state['logged_in'] = True
        st.session_state['user_email'] = email
        st.session_state['username'] = "TestUser"
        st.session_state['page'] = 'main'
        st.success("登录成功！")
        st.rerun()
        return True
    st.error('邮箱或密码错误')
    return False


def fetch_brands_models(country="哈萨克KOLESA"):
    cached_data = cache_handler.get_brands_models_cache(country)
    if cached_data:
        logging.info(f"从缓存获取品牌和型号数据: {country}")
        return cached_data["brands"], cached_data["models"]

    url = f"{API_BASE_URL}/api/brands_models?country={country}"
    try:
        response = requests.get(url, timeout=5)
        logging.info(f"Fetching brands/models from API: {url}, Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            brands = data.get("brands", ["Zeekr", "BYD"])
            models = data.get("models", {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]})
            cache_handler.set_brands_models_cache(country, {"brands": brands, "models": models})
            return brands, models
    except requests.RequestException as e:
        logging.error(f"Failed to fetch brands/models from API: {e}")
