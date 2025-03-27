import streamlit as st
import requests
import plotly.graph_objects as go
import logging
from payment_handler import init_stripe, display_subscription_plans, handle_subscription_status
from cache_handler import CacheHandler
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 从环境变量获取API配置
API_BASE_URL = os.getenv('API_BASE_URL', 'http://156.225.26.202:5000')

# 初始化Stripe和缓存系统
stripe_config = init_stripe()
cache_handler = CacheHandler()


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

    default_data = {"brands": ["Zeekr", "BYD"],
                    "models": {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]}}
    cache_handler.set_brands_models_cache(country, default_data)
    return default_data["brands"], default_data["models"]


if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_email'] = ''
    st.session_state['username'] = ''

if not st.session_state['logged_in']:
    st.title("登录")
    email = st.text_input("邮箱", key="login_email")
    password = st.text_input("密码", type="password", key="login_password")
    if st.button("登录", key="login_button"):
        # 临时硬编码登录
        if email == "hzhbond@hotmail.com" and password == "admin":
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = email
            st.session_state['username'] = "TestUser"
            st.success("登录成功！")
            st.rerun()
        else:
            st.error("邮箱或密码错误")
else:
    st.title("小贸助手 - 汽车数据分析平台")
    st.write(f"欢迎, {st.session_state['username']}!")
    if st.button("退出登录"):
        st.session_state['logged_in'] = False
        st.rerun()

    subscription_status = handle_subscription_status(st.session_state['user_email'])
    if subscription_status == "free":
        st.warning("您当前使用的是免费版本，5次体验查询机会，升级到高级版本无限次查询每日更新数据！")
        if st.button("查看订阅计划"):
            logging.info("Clicked '查看订阅计划'")
            display_subscription_plans()
    else:
        st.success("您当前是高级版用户，享有全部功能权限！")

    countries = ["俄罗斯AVITO", "俄罗斯AUTORU", "哈萨克KOLESA"]
    country = st.selectbox("国家", countries, index=2)
    brands, models = fetch_brands_models(country)
    brand = st.selectbox("品牌", brands)
    model = st.selectbox("型号", models[brand])
    if st.button("生成图表"):
        st.write("图表功能暂未实现")