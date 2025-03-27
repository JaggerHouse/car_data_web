import streamlit as st
import requests
import plotly.graph_objects as go
import json
import logging
import yaml
from payment_handler import init_stripe, display_subscription_plans, handle_subscription_status
from cache_handler import CacheHandler
import hashlib
import os
from dotenv import load_dotenv
import re  # 用于邮箱格式验证
import socket  # 用于获取 IP 地址
import time  # 新增：用于延时

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

# 获取客户端 IP 地址（本地测试用 socket，部署后可能需要调整）
def get_client_ip():
    try:
        # 本地测试时获取本机 IP
        return socket.gethostbyname(socket.gethostname())
    except:
        # 部署到云端时可能需要从请求头获取（Streamlit Cloud 可能需要额外配置）
        return "unknown_ip"

def register_user(email, company_name, password):
    try:
        from models import User, get_db_session
        with get_db_session() as db_session:
            # 验证邮箱格式
            if not is_valid_email(email):
                st.error('邮箱格式不正确，必须是 xxxx@xxxx.com 的形式')
                return False
            
            # 检查邮箱是否已注册
            existing_user = db_session.query(User).filter_by(email=email).first()
            if existing_user:
                st.error('该邮箱已注册')
                return False
            
            # 创建新用户，记录 IP 地址
            client_ip = get_client_ip()
            new_user = User(
                email=email,
                company_name=company_name,
                password=hash_password(password),
                username=company_name,
                last_used_ip=client_ip  # 记录注册时的 IP
            )
            db_session.add(new_user)
            db_session.commit()
            # 注册成功后显示提示框，等待 3 秒
            st.success("注册成功，请用邮箱登录")
            time.sleep(3)  # 新增：延时 3 秒
            return True
    except Exception as e:
        st.error(f'注册失败：{str(e)}')
        return False

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def login_user(email, password):
    try:
        from models import User, get_db_session
        with get_db_session() as db_session:
            user = db_session.query(User).filter_by(email=email).first()
            if user and user.password == hash_password(password):
                # 更新最后使用的 IP
                user.last_used_ip = get_client_ip()
                db_session.commit()
                st.session_state['logged_in'] = True
                st.session_state['user_email'] = user.email
                st.session_state['username'] = user.company_name
                return True
            st.error('邮箱或密码错误')
            return False
    except Exception as e:
        st.error(f'登录失败：{str(e)}')
        return False

def show_login_page():
    if 'logged_in' not in st.session_state:
        st.session_state['logged_in'] = False
    if st.session_state['logged_in']:
        return
    
    st.title("登录")
    
    tab1, tab2 = st.tabs(["登录", "注册"])
    
    with tab1:
        email = st.text_input("邮箱", key="login_email")
        password = st.text_input("密码", type="password", key="login_password")
        if st.button("登录", key="login_button"):
            if login_user(email, password):
                st.success("登录成功！")
                st.rerun()
    
    with tab2:
        email = st.text_input("邮箱", key="register_email")
        company_name = st.text_input("公司名称")
        password = st.text_input("密码", type="password", key="register_password")
        if st.button("注册", key="register_button"):
            if register_user(email, company_name, password):
                # 提示框已在 register_user 中显示并延时，这里直接刷新
                st.rerun()

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
    
    default_data = {"brands": ["Zeekr", "BYD"], "models": {"Zeekr": ["7X", "001", "全车型"], "BYD": ["Han", "Song", "全车型"]}}
    cache_handler.set_brands_models_cache(country, default_data)
    return default_data["brands"], default_data["models"]

def fetch_trend(country, brand, model, data_type, trend):
    if handle_subscription_status(st.session_state['user_email']) == 'free':
        from models import User, get_db_session
        with get_db_session() as db_session:
            user = db_session.query(User).filter_by(email=st.session_state['user_email']).first()
            client_ip = get_client_ip()
            
            # 检查当前 IP 的免费用户使用次数
            ip_users = db_session.query(User).filter_by(last_used_ip=client_ip, subscription_status='free').all()
            total_ip_usage = sum(user.usage_count for user in ip_users)
            
            # 限制：邮箱使用次数 >= 5 或 IP 使用次数 >= 5
            if user.usage_count >= 5 or total_ip_usage >= 5:
                st.warning('免费版已达使用上限，请升级到付费版继续使用')
                return {"x": ["免费版已达使用上限"], "y": [0]}
            
            # 更新当前用户的计数和 IP
            user.usage_count += 1
            user.last_used_ip = client_ip
            db_session.commit()
    
    cached_data = cache_handler.get_trend_cache(country, brand, model, data_type, trend)
    if cached_data:
        logging.info(f"从缓存获取趋势数据: {country}-{brand}-{model}")
        return cached_data
    
    url = f"{API_BASE_URL}/api/trend?country={country}&brand={brand}&model={model}&data_type={data_type}&type={trend}"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()["data"]
            cache_handler.set_trend_cache(country, brand, model, data_type, trend, data)
            return data
        return {"x": ["请求错误"], "y": [0]}
    except requests.RequestException as e:
        logging.error(f"Request Exception: {e}")
        return {"x": ["网络错误"], "y": [0]}

def format_price_range(price_range, currency):
    try:
        start, end = map(float, price_range.strip("()[]").split(", "))
        if currency in ["KZT", "RUB"]:
            return f"{start / 1000000:.2f}-{end / 1000000:.2f} 百万"
        return f"{int(start)}-{int(end)}"
    except:
        return price_range

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_email'] = ''
    st.session_state['username'] = ''

if not st.session_state['logged_in']:
    show_login_page()
else:
    st.title("小贸助手 - 汽车数据分析平台")

    # 在 st.title("小贸助手 - 汽车数据分析平台") 之后添加
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
                    # 这里可以保存到数据库或文件，暂时用 st.success 模拟
                    st.success("感谢您的建议！我们会认真考虑，并在采纳时通过邮箱联系您。")
                    # 示例：保存到本地文件
                    with open("suggestions.txt", "a", encoding="utf-8") as f:
                        f.write(f"邮箱: {contact_email}, 建议: {suggestion}, 时间: {time.ctime()}\n")
        
    col1, col2 = st.columns([3, 1])
    with col1:
        st.write(f"欢迎, {st.session_state['username']}!")
    with col2:
        if st.button("退出登录"):
            st.session_state['logged_in'] = False
            st.rerun()
    
    subscription_status = handle_subscription_status(st.session_state['user_email'])
    if subscription_status == "free":
        st.warning("您当前使用的是免费版本，5次体验查询机会，升级到高级版本无限次查询每日跟新数据！")
        if st.button("查看订阅计划"):
            display_subscription_plans()
    else:
        st.success("您当前是高级版用户，享有全部功能权限！")
    
    countries = ["俄罗斯AVITO", "俄罗斯AUTORU", "哈萨克KOLESA"]
    data_types = ["当日", "历史回溯"]
    
    country = st.selectbox("国家", countries, index=2)
    brands, models = fetch_brands_models(country)
    brand = st.selectbox("品牌", brands)
    model = st.selectbox("型号", models[brand])
    data_type = st.selectbox("数据类型", data_types)
    
    trend_options = ["价格区间-广告量"]
    if data_type == "当日" and country == "哈萨克KOLESA":
        trend_options.append("价格-观看量")
    elif data_type == "历史回溯":
        trend_options = ["车型-每日总广告量-时间", "车型-平均价格-时间"]
        if country == "哈萨克KOLESA":
            trend_options.append("车型-每日总观看量-时间")
    trend = st.selectbox("图表类型", trend_options)
    
    if st.button("生成图表"):
        data = fetch_trend(country, brand, model, data_type, trend)
        currency = "KZT" if country == "哈萨克KOLESA" else "RUB" if "俄罗斯" in country else "USD"
        
        if len(data["x"]) == 1 and data["x"][0] in ["暂无数据", "请求错误", "网络错误", "No Data", "免费版已达使用上限"]:
            st.write(data["x"][0])
        elif "价格区间-广告量" in trend:
            formatted_x = [format_price_range(x, currency) for x in data["x"]]
            fig = go.Figure(data=[go.Bar(
                x=formatted_x,
                y=data["y"],
                marker_color='blue',
                opacity=0.5,
                text=[f"区间: {x}<br>广告量: {y}" for x, y in zip(formatted_x, data["y"])],
                hoverinfo="text"
            )])
            fig.update_layout(
                title=f"{trend} ({country} - {brand} {model})",
                xaxis_title=f"价格区间 ({currency})",
                yaxis_title="广告数量",
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig)
        elif "价格-观看量" in trend:
            fig = go.Figure(data=[go.Scatter(
                x=data["x"],
                y=data["y"],
                mode='markers',
                marker=dict(color='blue', opacity=0.5)
            )])
            if "avg_price" in data and data["avg_price"]:
                fig.add_vline(x=data["avg_price"], line_dash="dash", line_color="red", 
                            annotation_text=f"平均价格: {data['avg_price']:,.0f}")
            fig.update_layout(
                title=f"{trend} ({country} - {brand} {model})",
                xaxis_title="价格",
                yaxis_title="观看量"
            )
            st.plotly_chart(fig)
        else:
            fig = go.Figure(data=[go.Scatter(
                x=data["x"],
                y=data["y"],
                mode='lines+markers',
                marker=dict(color='blue')
            )])
            fig.update_layout(
                title=f"{trend} ({country} - {brand} {model})",
                xaxis_title="时间",
                yaxis_title=trend.split("-")[1],
                xaxis_tickangle=-45
            )
            st.plotly_chart(fig)