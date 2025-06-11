"""
Streamlit Crypto Widget Application
Displays live cryptocurrency prices and 7-day historical charts
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import pandas as pd
import time
import hashlib
from crypto_api import CoinGeckoAPI, format_price, format_percentage, format_market_cap, format_volume, format_pair_price
from database import DatabaseManager

# Page configuration
st.set_page_config(
    page_title="Crypto Widget",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'selected_coins' not in st.session_state:
    st.session_state.selected_coins = ['bitcoin', 'ethereum', 'binancecoin', 'cardano', 'solana']
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True
if 'refresh_interval' not in st.session_state:
    st.session_state.refresh_interval = 30
if 'session_id' not in st.session_state:
    # Create a unique session ID for this user
    st.session_state.session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()
if 'use_database' not in st.session_state:
    st.session_state.use_database = True

# Initialize API and Database
@st.cache_resource
def get_api_client():
    """Initialize and cache the CoinGecko API client"""
    return CoinGeckoAPI()

@st.cache_resource
def get_database_manager():
    """Initialize and cache the database manager"""
    try:
        return DatabaseManager()
    except Exception as e:
        st.error(f"Database connection failed: {str(e)}")
        return None

api = get_api_client()
db = get_database_manager()

# Cache functions for better performance
@st.cache_data(ttl=300)  # Cache for 5 minutes
def load_supported_coins():
    """Load and cache supported coins"""
    try:
        return api.get_supported_coins()
    except Exception as e:
        st.error(f"Failed to load supported coins: {str(e)}")
        return []

@st.cache_data(ttl=60)  # Cache for 1 minute
def load_current_prices(coin_ids):
    """Load and cache current prices"""
    try:
        # Try to get from database first if enabled
        if st.session_state.use_database and db:
            cached_prices = db.get_latest_coin_prices(coin_ids)
            if cached_prices:
                # Check if data is recent (within last 2 minutes)
                for coin_id, data in cached_prices.items():
                    if 'last_updated_at' in data:
                        last_update = datetime.fromtimestamp(data['last_updated_at'])
                        if datetime.now() - last_update < timedelta(minutes=2):
                            return cached_prices
        
        # Fetch fresh data from API
        prices = api.get_current_prices(coin_ids)
        
        # Store in database if available
        if st.session_state.use_database and db and prices:
            try:
                db.store_coin_prices(prices)
            except Exception as db_error:
                st.warning(f"Database storage failed: {str(db_error)}")
        
        return prices
    except Exception as e:
        st.error(f"Failed to load current prices: {str(e)}")
        return {}

@st.cache_data(ttl=1800)  # Cache for 30 minutes
def load_historical_data(coin_id, days=7):
    """Load and cache historical data"""
    try:
        return api.get_historical_data(coin_id, days)
    except Exception as e:
        st.error(f"Failed to load historical data for {coin_id}: {str(e)}")
        return [], []

@st.cache_data(ttl=60)  # Cache for 1 minute
def load_trading_pairs():
    """Load and cache trading pairs data"""
    try:
        # Try to get from database first if enabled
        if st.session_state.use_database and db:
            cached_pairs = db.get_latest_trading_pairs()
            if cached_pairs:
                return cached_pairs
        
        # Fetch fresh data from API
        pairs = api.get_trading_pairs()
        
        # Store in database if available
        if st.session_state.use_database and db and pairs:
            try:
                db.store_trading_pairs(pairs)
            except Exception as db_error:
                st.warning(f"Database storage failed: {str(db_error)}")
        
        return pairs
    except Exception as e:
        st.error(f"Failed to load trading pairs: {str(e)}")
        return {}



def create_price_chart(timestamps, prices, coin_name, current_price):
    """Create an interactive price chart using Plotly"""
    if not timestamps or not prices:
        return None
    
    # Calculate price change for color
    price_change = ((current_price - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0
    line_color = '#00ff88' if price_change >= 0 else '#ff4444'
    
    fig = go.Figure()
    
    # Add price line
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=prices,
        mode='lines',
        name=f'{coin_name} Price',
        line=dict(color=line_color, width=2),
        hovertemplate='<b>%{y}</b><br>%{x}<extra></extra>',
        fill='tonexty' if price_change >= 0 else None,
        fillcolor=f'rgba(0, 255, 136, 0.1)' if price_change >= 0 else None
    ))
    
    # Add current price point
    fig.add_trace(go.Scatter(
        x=[timestamps[-1]],
        y=[current_price],
        mode='markers',
        name='Current Price',
        marker=dict(size=8, color=line_color, line=dict(width=2, color='white')),
        hovertemplate=f'<b>Current: {format_price(current_price)}</b><extra></extra>'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'{coin_name} - 7 Day Price Chart',
        xaxis_title='Date',
        yaxis_title='Price (USD)',
        hovermode='x unified',
        showlegend=False,
        height=400,
        margin=dict(l=0, r=0, t=40, b=0),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            gridcolor='rgba(128,128,128,0.2)',
            showgrid=True
        ),
        yaxis=dict(
            gridcolor='rgba(128,128,128,0.2)',
            showgrid=True,
            tickformat='$,.2f'
        )
    )
    
    return fig



def display_pair_card(pair_name, pair_data):
    """Display a trading pair card"""
    try:
        price = pair_data['price']
        change_24h = pair_data.get('change_24h', 0)
        base = pair_data.get('base', '')
        quote = pair_data.get('quote', '')
        
        # Determine color for price change
        change_color = "green" if change_24h >= 0 else "red"
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.metric(
                label=f"{pair_name}",
                value=format_pair_price(price, pair_name),
                delta=format_percentage(change_24h) if change_24h != 0 else None
            )
        
        with col2:
            st.write(f"**Base:** {base}")
            st.write(f"**Quote:** {quote}")
            
    except KeyError as e:
        st.error(f"Missing data for {pair_name}: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying {pair_name}: {str(e)}")



def display_price_card(coin_id, coin_data, coin_info):
    """Display a price card for a cryptocurrency"""
    try:
        price = coin_data['usd']
        change_24h = coin_data.get('usd_24h_change', 0)
        volume_24h = coin_data.get('usd_24h_vol', coin_data.get('total_volume', 0))
        market_cap = coin_data.get('usd_market_cap', coin_data.get('market_cap', 0))
        
        # Determine color for price change
        change_color = "green" if change_24h >= 0 else "red"
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.metric(
                label=f"{coin_info['name']} ({coin_info['symbol']})",
                value=format_price(price),
                delta=format_percentage(change_24h)
            )
        
        with col2:
            st.write(f"**Market Cap:** {format_market_cap(market_cap)}")
            st.write(f"**24h Volume:** {format_volume(volume_24h)}")
            
    except KeyError as e:
        st.error(f"Missing data for {coin_id}: {str(e)}")
    except Exception as e:
        st.error(f"Error displaying {coin_id}: {str(e)}")

def main():
    """Main application function"""
    st.title("🚀 Crypto Widget Dashboard")
    st.markdown("Real-time cryptocurrency prices and 7-day historical charts")
    
    # Sidebar configuration
    with st.sidebar:
        st.header("⚙️ Settings")
        
        # Database status indicator
        if db:
            st.success("🗄️ Database Connected")
            st.session_state.use_database = st.checkbox("Use Database Cache", value=st.session_state.use_database)
        else:
            st.error("🗄️ Database Unavailable")
            st.session_state.use_database = False
        
        # Load supported coins
        with st.spinner("Loading supported coins..."):
            supported_coins = load_supported_coins()
        
        if not supported_coins:
            st.error("Could not load cryptocurrency data. Please check your internet connection.")
            return
        
        # Create options for multiselect
        coin_options = {f"{coin['name']} ({coin['symbol']})": coin['id'] for coin in supported_coins}
        
        # Coin selection
        st.subheader("Select Cryptocurrencies")
        selected_coin_names = st.multiselect(
            "Choose coins to display:",
            options=list(coin_options.keys()),
            default=[name for name, id in coin_options.items() if id in st.session_state.selected_coins[:5]],
            help="Select up to 10 cryptocurrencies to monitor"
        )
        
        # Update selected coins
        st.session_state.selected_coins = [coin_options[name] for name in selected_coin_names]
        
        if len(st.session_state.selected_coins) > 10:
            st.warning("Please select maximum 10 coins for optimal performance")
            st.session_state.selected_coins = st.session_state.selected_coins[:10]
        
        # Save preferences to database
        if st.session_state.use_database and db:
            try:
                db.save_user_preferences(
                    st.session_state.session_id,
                    st.session_state.selected_coins,
                    st.session_state.auto_refresh,
                    st.session_state.refresh_interval
                )
            except Exception as db_error:
                st.warning(f"Failed to save preferences: {str(db_error)}")
        
        # Auto-refresh settings
        st.subheader("Auto Refresh")
        st.session_state.auto_refresh = st.checkbox("Enable auto refresh", value=st.session_state.auto_refresh)
        
        if st.session_state.auto_refresh:
            st.session_state.refresh_interval = st.select_slider(
                "Refresh interval (seconds):",
                options=[15, 30, 60, 120, 300],
                value=st.session_state.refresh_interval
            )
        
        # Manual refresh button
        if st.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        # Last update info
        if st.session_state.last_update:
            st.caption(f"Last updated: {st.session_state.last_update.strftime('%H:%M:%S')}")
    
    # Main content
    if not st.session_state.selected_coins:
        st.info("👈 Please select at least one cryptocurrency from the sidebar to get started.")
        return
    
    # Load current prices
    with st.spinner("Loading current prices..."):
        current_prices = load_current_prices(st.session_state.selected_coins)
    
    if not current_prices:
        st.error("Could not load current prices. Please try again later.")
        return
    
    # Create coin info mapping
    coin_info_map = {coin['id']: coin for coin in supported_coins}
    
    # Display price cards
    st.subheader("💰 Current Prices")
    
    # Create columns for price cards
    cols = st.columns(min(len(st.session_state.selected_coins), 3))
    
    for idx, coin_id in enumerate(st.session_state.selected_coins):
        col_idx = idx % len(cols)
        
        with cols[col_idx]:
            if coin_id in current_prices and coin_id in coin_info_map:
                with st.container():
                    st.markdown("---")
                    display_price_card(coin_id, current_prices[coin_id], coin_info_map[coin_id])
            else:
                st.error(f"No data available for {coin_id}")
    
    # Display trading pairs section
    st.subheader("🔄 Trading Pairs")
    
    with st.spinner("Loading trading pairs..."):
        trading_pairs = load_trading_pairs()
    
    if trading_pairs:
        # Display trading pair cards
        pair_cols = st.columns(3)
        pair_names = list(trading_pairs.keys())
        
        for idx, pair_name in enumerate(pair_names):
            col_idx = idx % len(pair_cols)
            
            with pair_cols[col_idx]:
                with st.container():
                    st.markdown("---")
                    display_pair_card(pair_name, trading_pairs[pair_name])
        

    
    # Display charts
    st.subheader("📈 7-Day Price Charts")
    
    # Create tabs for each selected coin
    if len(st.session_state.selected_coins) > 1:
        tab_names = [coin_info_map.get(coin_id, {}).get('symbol', coin_id).upper() 
                    for coin_id in st.session_state.selected_coins]
        tabs = st.tabs(tab_names)
        
        for idx, coin_id in enumerate(st.session_state.selected_coins):
            with tabs[idx]:
                display_coin_chart(coin_id, current_prices, coin_info_map)
    else:
        # Single coin display
        coin_id = st.session_state.selected_coins[0]
        display_coin_chart(coin_id, current_prices, coin_info_map)
    
    # Update last update time
    st.session_state.last_update = datetime.now()
    
    # Auto-refresh logic
    if st.session_state.auto_refresh:
        time.sleep(st.session_state.refresh_interval)
        st.rerun()

def display_coin_chart(coin_id, current_prices, coin_info_map):
    """Display chart for a specific coin"""
    if coin_id not in current_prices or coin_id not in coin_info_map:
        st.error(f"No data available for {coin_id}")
        return
    
    coin_info = coin_info_map[coin_id]
    current_price = current_prices[coin_id]['usd']
    
    with st.spinner(f"Loading {coin_info['name']} chart..."):
        timestamps, prices = load_historical_data(coin_id, 7)
    
    if timestamps and prices:
        chart = create_price_chart(timestamps, prices, coin_info['name'], current_price)
        if chart:
            st.plotly_chart(chart, use_container_width=True)
            
            # Additional statistics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("7d High", format_price(max(prices)))
            with col2:
                st.metric("7d Low", format_price(min(prices)))
            with col3:
                price_change_7d = ((current_price - prices[0]) / prices[0]) * 100 if prices[0] != 0 else 0
                st.metric("7d Change", format_percentage(price_change_7d))
            with col4:
                avg_price = sum(prices) / len(prices) if prices else 0
                st.metric("7d Average", format_price(avg_price))
    else:
        st.warning(f"Could not load historical data for {coin_info['name']}")

if __name__ == "__main__":
    main()
