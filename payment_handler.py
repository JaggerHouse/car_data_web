import stripe
import streamlit as st
import os
from datetime import datetime

# 从环境变量加载配置
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def init_stripe():
    return {
        "publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY"),
        "secret_key": os.getenv("STRIPE_SECRET_KEY"),
        "webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET")
    }


def create_checkout_session(price_id: str, user_email: str):
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url="https://xiaomaoassistant.streamlit.app/?success=true",
            cancel_url="https://xiaomaoassistant.streamlit.app/?canceled=true",
            customer_email=user_email,
        )
        return checkout_session
    except Exception as e:
        st.error(f"创建支付会话失败: {str(e)}")
        return None


def handle_subscription_status(user_email: str) -> str:
    # 临时逻辑：后续接入数据库或 Stripe API
    # 当前返回 "free"，支付成功后可通过 URL 参数临时更新
    query_params = st.query_params
    if "success" in query_params and query_params["success"] == "true":
        return "premium"
    return "free"


def display_subscription_plans():
    plans = {
        "premium": {
            "name": "高级版",
            "price": 299,
            "price_id": os.getenv("STRIPE_PREMIUM_PRICE_ID", "price_premium"),
            "features": [
                "无限次数据查询",
                "实时数据更新",
                "API访问权限"
            ]
        }
    }

    st.subheader("订阅计划")

    st.markdown(f"### {plans['premium']['name']}")
    st.markdown(f"¥{plans['premium']['price']}/月")
    for feature in plans['premium']['features']:
        st.markdown(f"- {feature}")
    if st.button("选择高级版", key="premium"):
        if 'user_email' in st.session_state:
            session = create_checkout_session(
                plans['premium']['price_id'],
                st.session_state['user_email']
            )
            if session:
                # 显示支付按钮并自动跳转
                st.markdown(f"正在跳转到支付页面，请稍候...")
                st.markdown(f'<meta http-equiv="refresh" content="0;url={session.url}">', unsafe_allow_html=True)
        else:
            st.warning("请先登录")