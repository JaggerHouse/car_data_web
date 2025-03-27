import stripe
import yaml
from typing import Dict, Any
import streamlit as st
import os

def load_stripe_config() -> Dict[str, Any]:
    with open('stripe_config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    # 从环境变量中获取敏感配置
    config['stripe']['publishable_key'] = os.getenv('STRIPE_PUBLISHABLE_KEY')
    config['stripe']['secret_key'] = os.getenv('STRIPE_SECRET_KEY')
    config['stripe']['webhook_secret'] = os.getenv('STRIPE_WEBHOOK_SECRET')
    return config

def init_stripe():
    stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
    return {
        'stripe': {
            'publishable_key': os.getenv('STRIPE_PUBLISHABLE_KEY'),
            'secret_key': os.getenv('STRIPE_SECRET_KEY'),
            'webhook_secret': os.getenv('STRIPE_WEBHOOK_SECRET')
        }
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
            success_url=st.get_url() + '?success=true',
            cancel_url=st.get_url() + '?canceled=true',
            customer_email=user_email,
        )
        return checkout_session
    except Exception as e:
        st.error(f"创建支付会话失败: {str(e)}")
        return None

def handle_subscription_status(user_email: str) -> str:
    try:
        from models import get_db_session, User
        db_session = get_db_session()
        user = db_session.query(User).filter_by(email=user_email).first()
        
        if not user:
            return "free"
            
        if user.subscription_status in ['basic', 'premium']:
            # 检查订阅是否过期
            if user.subscription_end_date and user.subscription_end_date > datetime.utcnow():
                return user.subscription_status
        
        return "free"
    except Exception as e:
        st.error(f"获取订阅状态失败: {str(e)}")
        return "free"
    finally:
        if 'db_session' in locals():
            db_session.close()

def display_subscription_plans():
    config = load_stripe_config()
    plans = config['subscription_plans']
    
    st.subheader("订阅计划")
    
    st.markdown(f"### {plans['premium']['name']}")
    st.markdown(f"¥{plans['premium']['price']}/月")
    for feature in plans['premium']['features']:
        st.markdown(f"- {feature}")
    if st.button("选择高级版", key="premium"):
        if 'user_email' in st.session_state:
            session = create_checkout_session(
                plans['premium']['price_id'],
                st.session_state.user_email
            )
            if session:
                st.markdown(f'<script>window.location.href="{session.url}";</script>', unsafe_allow_html=True)
        else:
            st.warning("请先登录")