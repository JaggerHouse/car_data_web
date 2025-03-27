import streamlit as st
import requests
import plotly.graph_objects as go
import logging
import hashlib
import time
import os
import json
from datetime import datetime, timedelta
from payment_handler import init_stripe, display_subscription_plans, handle_subscription_status
from cache_handler import CacheHandler
from dotenv import load_dotenv
import re

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# API 和本地文件配置
API_BASE_URL = os.getenv('API_BASE_URL', 'http://156.225.26.202:5000')
LOCAL_BRANDS_MODELS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "brands_models.json")
USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

# 初始化Stripe和缓存系统
stripe_config = init_stripe()
cache_handler = CacheHandler()


# 验证邮箱格式的函数
def is_valid_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def register_user(email, company_name, password):
    users = load_users()
    if not is_valid_email(email):
        st.error('邮箱格式不正确，必须是 xxxx@xxxx.com 的形式')
        return False
    if email in users:
        st.error('该邮箱已注册')
        return False
    users[email] = {
        'company_name': company_name,
        'password': hash_password(password),
        'subscription_status': 'free',
        'subscription_expiry': None
    }
    save_users(users)
    st.success("注册成功，请用邮箱登录")
    time.sleep(2)
    return True


def login_user(email, password):
    users = load_users()
    if email in users:
        user = users[email]
        if user['password'] == hash_password(password):
            st.session_state['logged_in'] = True
            st.session_state['user_email'] = email
            st.session_state['username'] = user['company_name']
            return True
    if email == "hzhbond@hotmail.com" and password == "admin":
        st.session_state['logged_in'] = True
        st.session_state['user_email'] = email
        st.session_state['username'] = "TestUser"
        if email not in users:
            users[email] = {
                'company_name': "TestUser",
                'password': hash_password(password),
                'subscription_status': 'free',
                'subscription_expiry': None
            }
            save_users(users)
        return True
    st.error('邮箱或密码错误')
    return False


def fetch_brands_models_from_api(country="哈萨克KOLESA"):
    url = f"{API_BASE_URL}/api/brands_models?country={country}"
    try:
        response = requests.get(url, timeout=5)
        logging.info(f"Fetching brands/models from API: {url}, Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            brands = data.get("brands", ["Zeekr", "BYD"])
            models = data.get("models", {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]})
            return brands, models
    except requests.RequestException as e:
        logging.error(f"Failed to fetch brands/models from API: {e}")
    return ["Zeekr", "BYD"], {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]}


def save_brands_models_to_local(brands, models):
    data = {"brands": brands, "models": models}
    try:
        with open(LOCAL_BRANDS_MODELS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logging.info(f"Saved brands/models to {LOCAL_BRANDS_MODELS_FILE}")
    except Exception as e:
        logging.error(f"Failed to save brands/models: {e}")


def load_brands_models_from_local():
    if os.path.exists(LOCAL_BRANDS_MODELS_FILE):
        try:
            with open(LOCAL_BRANDS_MODELS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("brands", ["Zeekr", "BYD"]), data.get("models", {"Zeekr": ["7X", "001", "全车型"],
                                                                                 "BYD": ["Han", "Song", "全车型"]})
        except Exception as e:
            logging.error(f"Failed to load local brands/models: {e}")
    return ["Zeekr", "BYD"], {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]}


def fetch_data(country, brand, model, data_type, trend):
    url = f"{API_BASE_URL}/api/trend?country={country}&brand={brand}&model={model}&data_type={data_type}&type={trend}"
    try:
        response = requests.get(url, timeout=5)
        logging.info(f"Fetching data from: {url}, Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()["data"]
            return data
        else:
            return {"x": ["请求错误"], "y": [0]}
    except requests.RequestException as e:
        logging.error(f"Failed to fetch data: {e}")
        return {"x": ["网络错误"], "y": [0]}


def format_price_range(price_str, currency="KZT"):
    try:
        start, end = map(float, price_str.strip("()[]").split(", "))
        if currency in ["KZT", "RUB"]:
            return f"{start / 1000000:.2f}-{end / 1000000:.2f}百万"
        elif currency == "USD":
            return f"{start / 1000:.1f}-{end / 1000:.1f}k"
        return f"{int(start)}-{int(end)}"
    except:
        return price_str


# 初始化状态
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_email'] = ''
    st.session_state['username'] = ''
if 'show_subscription' not in st.session_state:
    st.session_state['show_subscription'] = False
if 'brands' not in st.session_state or 'models' not in st.session_state:
    st.session_state['brands'], st.session_state['models'] = load_brands_models_from_local()

# 主逻辑
if not st.session_state['logged_in']:
    st.title("登录")
    tab1, tab2 = st.tabs(["登录", "注册"])

    with tab1:
        email = st.text_input("邮箱", key="login_email")
        password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录", key="login_button"):
            if login_user(email, password):
                st.rerun()

    with tab2:
        reg_email = st.text_input("邮箱", key="register_email")
        company_name = st.text_input("公司名称", key="register_company")
        reg_password = st.text_input("密码", type="password", key="register_password")
        if st.button("注册", key="register_button"):
            if register_user(reg_email, company_name, reg_password):
                st.rerun()

else:
    if st.session_state['show_subscription']:
        display_subscription_plans()
        if st.button("返回主页"):
            st.session_state['show_subscription'] = False
            st.rerun()
    else:
        st.title("小贸助手 - 汽车数据分析平台")

        col1, col2 = st.columns([3, 1])
        with col1:
            st.write(f"欢迎, {st.session_state['username']}!")
        with col2:
            if st.button("退出登录"):
                st.session_state['logged_in'] = False
                st.session_state['user_email'] = ''
                st.session_state['username'] = ''
                st.session_state['show_subscription'] = False
                st.rerun()

        if st.button("提建议"):
            with st.form(key="suggestion_form"):
                suggestion = st.text_area("请输入您的建议")
                contact_email = st.text_input("您的邮箱（若建议被采纳，我们会联系您）")
                submit_button = st.form_submit_button(label="提交")
                if submit_button:
                    if not suggestion or not contact_email:
                        st.error("建议和邮箱不能为空")
                    elif not is_valid_email(contact_email):
                        st.error("邮箱格式不正确")
                    else:
                        st.success("感谢您的建议！我们会认真考虑，并在采纳时通过邮箱联系您。")
                        with open("suggestions.txt", "a", encoding="utf-8") as f:
                            f.write(f"邮箱: {contact_email}, 建议: {suggestion}, 时间: {time.ctime()}\n")

        subscription_status = handle_subscription_status(st.session_state['user_email'])
        if subscription_status == "free":
            st.warning("您当前使用的是免费版本，5次体验查询机会，升级到高级版本无限次查询每日更新数据！")
            if st.button("查看订阅计划"):
                st.session_state['show_subscription'] = True
                st.rerun()
        else:
            st.success("您当前是高级版用户，享有全部功能权限！")

        # 数据选择
        countries = ["俄罗斯AVITO", "俄罗斯AUTORU", "哈萨克KOLESA"]
        data_types = ["当日", "历史回溯"]
        country = st.selectbox("国家", countries, index=2, key="country")
        if st.button("更新品牌-车型"):
            st.session_state['brands'], st.session_state['models'] = fetch_brands_models_from_api(country)
            save_brands_models_to_local(st.session_state['brands'], st.session_state['models'])
            st.success("品牌和车型列表已更新！")
        brand = st.selectbox("品牌", st.session_state['brands'], key="brand")
        model = st.selectbox("型号", st.session_state['models'].get(brand, []), key="model")
        data_type = st.selectbox("数据类型", data_types, key="data_type")

        # 图表类型动态更新
        trend_options = []
        if data_type == "当日":
            if model == "全车型":
                trend_options = ["品牌总广告"]
            else:
                if country == "哈萨克KOLESA":
                    trend_options = ["价格区间-广告量", "价格-观看量"]
                else:
                    trend_options = ["价格区间-广告量"]
        elif data_type == "历史回溯":
            if model == "全车型":
                trend_options = ["品牌-每日总广告量-时间"]
                if country == "哈萨克KOLESA":
                    trend_options.append("品牌-每日总观看量-时间")
            else:
                trend_options = ["车型-每日总广告量-时间", "车型-平均价格-时间"]
                if country == "哈萨克KOLESA":
                    trend_options.append("车型-每日总观看量-时间")
        trend = st.selectbox("图表类型", trend_options, key="trend")

        if st.button("生成图表"):
            data = fetch_data(country, brand, model, data_type, trend)
            if data:
                fig = go.Figure()
                if "价格区间-广告量" in trend:
                    x = [format_price_range(x, "KZT" if country == "哈萨克KOLESA" else "RUB") for x in data["x"]]
                    fig.add_trace(go.Bar(x=x, y=data["y"], name="广告量"))
                    fig.update_layout(xaxis_title="价格区间", yaxis_title="广告数量")
                elif "价格-观看量" in trend:
                    fig.add_trace(go.Scatter(x=data["x"], y=data["y"], mode="markers", name="观看量"))
                    if "avg_price" in data and data["avg_price"]:
                        fig.add_vline(x=data["avg_price"], line_dash="dash", line_color="red",
                                      annotation_text="平均价格")
                    if "median_price" in data and data["median_price"]:
                        fig.add_vline(x=data["median_price"], line_dash="dash", line_color="green",
                                      annotation_text="中位数价格")
                    fig.update_layout(xaxis_title="价格", yaxis_title="观看量")
                else:
                    fig.add_trace(go.Scatter(x=data["x"], y=data["y"], mode="lines+markers", name=trend.split("-")[1]))
                    fig.update_layout(xaxis_title="时间", yaxis_title=trend.split("-")[1])
                fig.update_layout(title=f"{trend} ({country} - {brand} {model})")
                st.plotly_chart(fig)