import pandas as pd
import numpy as np
import streamlit as st
import yfinance as yf
from datetime import datetime, timedelta
import pytz
import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from chess_piece.queen_hive import init_queenbee, refresh_account_info
from chess_piece.pollen_db import PollenDatabase
from chess_piece.king import hive_master_root
from pq_auth import signin_main
import logging

# Set page config FIRST - before any other Streamlit commands
st.set_page_config(
    page_title="Options Trading",
    page_icon="📈",
    layout="wide"
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
main_root = hive_master_root()
load_dotenv(os.path.join(main_root, ".env"))

# Set pandas options
pd.options.mode.chained_assignment = None

# Timezone setup
est = pytz.timezone("US/Eastern")

# Check authentication
if 'authorized_user' not in st.session_state:
    signin_main("options")

if st.session_state["authorized_user"] != True:
    st.error("You do not have permissions to access this page")
    st.stop()

def get_alpaca_api():
    """Initialize and return Alpaca API connection"""
    try:
        api_key = os.getenv('ALPACA_API_KEY')
        api_secret = os.getenv('ALPACA_SECRET_KEY')
        base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        
        if not api_key or not api_secret:
            st.error("Alpaca API credentials not found. Please check your environment variables.")
            return None
            
        api = tradeapi.REST(api_key, api_secret, base_url, api_version='v2')
        return api
    except Exception as e:
        st.error(f"Failed to initialize Alpaca API: {e}")
        return None

def fetch_options_chain(ticker, expiration_date=None):
    """Fetch options chain for a given ticker"""
    try:
        stock = yf.Ticker(ticker)
        
        # Get options expiration dates
        expirations = stock.options
        if not expirations:
            st.warning(f"No options data available for {ticker}")
            return None, None
            
        # Use provided expiration or the first available
        if expiration_date is None:
            expiration_date = expirations[0]
        elif expiration_date not in expirations:
            st.warning(f"Expiration date {expiration_date} not available. Using {expirations[0]}")
            expiration_date = expirations[0]
            
        # Get options chain
        options_chain = stock.option_chain(expiration_date)
        
        return options_chain, expiration_date
    except Exception as e:
        st.error(f"Error fetching options chain for {ticker}: {e}")
        return None, None

def filter_options_by_timeframe(options_chain, timeframe):
    """Filter options by timeframe (1D, 5D, 1M, 3M, 6M, 1Y)"""
    if not options_chain:
        return None, None
        
    calls = options_chain.calls
    puts = options_chain.puts
    
    # Calculate days to expiration
    current_date = datetime.now(est).date()
    expiration_date = pd.to_datetime(options_chain.calls['expiration'].iloc[0]).date()
    days_to_exp = (expiration_date - current_date).days
    
    # Filter based on timeframe
    timeframe_days = {
        '1D': 1,
        '5D': 5,
        '1M': 30,
        '3M': 90,
        '6M': 180,
        '1Y': 365
    }
    
    target_days = timeframe_days.get(timeframe, 30)
    
    # For now, return all options (in a real implementation, you'd filter by expiration)
    return calls, puts

def generate_option_suggestions(calls, puts, current_price, strategy_type="call"):
    """Generate simple option suggestions based on current price and strategy"""
    suggestions = []
    
    if strategy_type == "call":
        # Find calls near the money
        near_money_calls = calls[
            (calls['strike'] >= current_price * 0.95) & 
            (calls['strike'] <= current_price * 1.05)
        ].head(5)
        
        for _, option in near_money_calls.iterrows():
            suggestions.append({
                'type': 'Call',
                'strike': option['strike'],
                'bid': option['bid'],
                'ask': option['ask'],
                'volume': option['volume'],
                'open_interest': option['openInterest'],
                'implied_volatility': option['impliedVolatility']
            })
    
    elif strategy_type == "put":
        # Find puts near the money
        near_money_puts = puts[
            (puts['strike'] >= current_price * 0.95) & 
            (puts['strike'] <= current_price * 1.05)
        ].head(5)
        
        for _, option in near_money_puts.iterrows():
            suggestions.append({
                'type': 'Put',
                'strike': option['strike'],
                'bid': option['bid'],
                'ask': option['ask'],
                'volume': option['volume'],
                'open_interest': option['openInterest'],
                'implied_volatility': option['impliedVolatility']
            })
    
    return suggestions

def place_option_order(api, symbol, option_symbol, quantity, side, order_type="market", limit_price=None):
    """Place an options order through Alpaca API"""
    try:
        if order_type == "market":
            order = api.submit_order(
                symbol=option_symbol,
                qty=quantity,
                side=side,
                type="market",
                time_in_force="gtc"
            )
        elif order_type == "limit":
            if not limit_price:
                st.error("Limit price required for limit orders")
                return None
            order = api.submit_order(
                symbol=option_symbol,
                qty=quantity,
                side=side,
                type="limit",
                time_in_force="gtc",
                limit_price=limit_price
            )
        
        return order
    except Exception as e:
        st.error(f"Error placing order: {e}")
        return None

def save_option_order(order_data, client_user, prod=False):
    """Save option order to database using existing PollenDatabase framework"""
    try:
        # Create a comprehensive order record
        order_record = {
            'order_id': order_data.get('id'),
            'symbol': order_data.get('symbol'),
            'side': order_data.get('side'),
            'quantity': order_data.get('qty'),
            'order_type': order_data.get('order_type'),
            'status': order_data.get('status'),
            'created_at': datetime.now(est).isoformat(),
            'client_order_id': order_data.get('client_order_id'),
            'client_user': client_user,
            'prod': prod,
            'order_class': 'option',
            'asset_class': 'option'
        }
        
        # Use existing PollenDatabase framework
        table_name = 'option_orders' if prod else 'option_orders_sandbox'
        
        # Create table if it doesn't exist
        PollenDatabase.create_table_if_not_exists(table_name)
        
        # Save the order
        PollenDatabase.upsert_data(table_name, order_data.get('id'), order_record)
        
        logger.info(f"Option order saved: {order_record}")
        return True
    except Exception as e:
        logger.error(f"Error saving option order: {e}")
        return False

def get_option_orders(client_user, prod=False):
    """Retrieve option orders from database"""
    try:
        table_name = 'option_orders' if prod else 'option_orders_sandbox'
        
        # This is a simplified retrieval - in practice you'd want more sophisticated querying
        # For now, we'll return the session state orders
        return st.session_state.get('option_orders', [])
    except Exception as e:
        logger.error(f"Error retrieving option orders: {e}")
        return []

def main():
    
    st.title("📈 Options Trading Dashboard")
    st.markdown("---")
    
    # Get user and environment info
    client_user = st.session_state.get('username', 'unknown')
    prod = st.session_state.get('prod', False)
    
    # Display environment info
    env_text = "Live Account" if prod else "Sandbox Account"
    st.info(f"Environment: {env_text} | User: {client_user}")
    
    # Initialize session state
    if 'option_orders' not in st.session_state:
        st.session_state['option_orders'] = []
    
    # Initialize queen bee for API access
    try:
        qb = init_queenbee(client_user=client_user, prod=prod, queen_king=True, api=True, init=True)
        api = qb.get('api')
        QUEEN_KING = qb.get('QUEEN_KING')
        
        if not api:
            st.error("Failed to initialize API connection. Please check your credentials.")
            st.stop()
            
        # Display account info
        with st.expander("Account Information", expanded=False):
            try:
                account_info = refresh_account_info(api=api)
                if account_info:
                    # Debug: show what we received
                    st.write("Debug - Account info keys:", list(account_info.keys()) if isinstance(account_info, dict) else "Not a dict")
                    
                    # Use the converted info which has proper numeric formatting
                    converted_info = account_info.get('info_converted', {})
                    if converted_info:
                        st.json(converted_info)
                    else:
                        # Fallback: display basic account info in a readable format
                        raw_info = account_info.get('info', {})
                        if hasattr(raw_info, '__dict__'):
                            # Extract basic info from the account object
                            basic_info = {
                                'account_number': getattr(raw_info, 'account_number', 'N/A'),
                                'status': getattr(raw_info, 'status', 'N/A'),
                                'currency': getattr(raw_info, 'currency', 'N/A'),
                                'buying_power': getattr(raw_info, 'buying_power', 'N/A'),
                                'cash': getattr(raw_info, 'cash', 'N/A'),
                                'portfolio_value': getattr(raw_info, 'portfolio_value', 'N/A')
                            }
                            st.json(basic_info)
                        else:
                            st.warning("Account info format not recognized")
                else:
                    st.warning("No account information received")
            except Exception as e:
                st.warning(f"Could not fetch account info: {e}")
                st.write("Full error:", str(e))
                
    except Exception as e:
        st.error(f"Failed to initialize trading environment: {e}")
        st.stop()
    
    # Sidebar for input parameters
    with st.sidebar:
        st.header("Options Parameters")
        
        # Ticker input
        ticker = st.text_input("Enter Ticker Symbol", value="AAPL", help="Enter the stock symbol (e.g., AAPL, TSLA)")
        
        # Timeframe selection
        timeframe = st.selectbox(
            "Select Timeframe",
            options=["1D", "5D", "1M", "3M", "6M", "1Y"],
            index=2,  # Default to 1M
            help="Filter options by expiration timeframe"
        )
        
        # Strategy type
        strategy_type = st.selectbox(
            "Strategy Type",
            options=["call", "put"],
            help="Choose between call or put options"
        )
        
        # Fetch options button
        fetch_options = st.button("Fetch Options Chain", type="primary")
    
    # Main content area
    if fetch_options and ticker:
        with st.spinner(f"Fetching options data for {ticker}..."):
            # Get current stock price
            try:
                stock = yf.Ticker(ticker)
                current_price = stock.history(period="1d")['Close'].iloc[-1]
                st.success(f"Current {ticker} price: ${current_price:.2f}")
            except Exception as e:
                st.error(f"Could not fetch current price for {ticker}: {e}")
                current_price = None
            
            # Fetch options chain
            options_chain, expiration_date = fetch_options_chain(ticker)
            
            if options_chain:
                st.success(f"Options chain loaded for expiration: {expiration_date}")
                
                # Filter options by timeframe
                calls, puts = filter_options_by_timeframe(options_chain, timeframe)
                
                if calls is not None and puts is not None:
                    # Display options data
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("📞 Call Options")
                        if not calls.empty:
                            # Display key columns
                            display_calls = calls[['strike', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].head(10)
                            st.dataframe(display_calls, use_container_width=True)
                        else:
                            st.info("No call options available")
                    
                    with col2:
                        st.subheader("📉 Put Options")
                        if not puts.empty:
                            # Display key columns
                            display_puts = puts[['strike', 'bid', 'ask', 'volume', 'openInterest', 'impliedVolatility']].head(10)
                            st.dataframe(display_puts, use_container_width=True)
                        else:
                            st.info("No put options available")
                    
                    # Generate suggestions
                    if current_price:
                        st.subheader("💡 Option Suggestions")
                        suggestions = generate_option_suggestions(calls, puts, current_price, strategy_type)
                        
                        if suggestions:
                            suggestions_df = pd.DataFrame(suggestions)
                            st.dataframe(suggestions_df, use_container_width=True)
                            
                            # Trading interface
                            st.subheader("🛒 Place Order")
                            
                            with st.form("option_order_form"):
                                col1, col2, col3 = st.columns(3)
                                
                                with col1:
                                    selected_option = st.selectbox(
                                        "Select Option",
                                        options=[f"{opt['type']} ${opt['strike']:.0f}" for opt in suggestions],
                                        help="Choose an option from the suggestions"
                                    )
                                
                                with col2:
                                    quantity = st.number_input("Quantity", min_value=1, value=1, help="Number of contracts")
                                
                                with col3:
                                    order_side = st.selectbox("Side", options=["buy", "sell"], help="Buy or sell the option")
                                
                                order_type = st.selectbox(
                                    "Order Type",
                                    options=["market", "limit"],
                                    help="Market order executes immediately, limit order sets a price"
                                )
                                
                                limit_price = None
                                if order_type == "limit":
                                    limit_price = st.number_input("Limit Price", min_value=0.01, value=0.01, step=0.01)
                                
                                submit_order = st.form_submit_button("Place Order", type="primary")
                                
                                if submit_order:
                                    # Get the selected option details
                                    option_index = [f"{opt['type']} ${opt['strike']:.0f}" for opt in suggestions].index(selected_option)
                                    selected_option_data = suggestions[option_index]
                                    
                                    # Create option symbol (this is a simplified version)
                                    # In reality, you'd need to construct the proper option symbol format
                                    option_symbol = f"{ticker}{expiration_date.replace('-', '')}{selected_option_data['strike']:08.0f}{'C' if selected_option_data['type'] == 'Call' else 'P'}"
                                    
                                    # Place the order
                                    with st.spinner("Placing order..."):
                                        order = place_option_order(
                                            api=api,
                                            symbol=ticker,
                                            option_symbol=option_symbol,
                                            quantity=quantity,
                                            side=order_side,
                                            order_type=order_type,
                                            limit_price=limit_price
                                        )
                                        
                                        if order:
                                            st.success("Order placed successfully!")
                                            
                                            # Display order details
                                            order_details = {
                                                'order_id': order.id,
                                                'symbol': order.symbol,
                                                'side': order.side,
                                                'quantity': order.qty,
                                                'status': order.status,
                                                'order_type': order_type,
                                                'created_at': datetime.now(est).strftime("%Y-%m-%d %H:%M:%S")
                                            }
                                            
                                            st.json(order_details)
                                            
                                            # Save order to database
                                            order_data = {
                                                'id': order.id,
                                                'symbol': order.symbol,
                                                'side': order.side,
                                                'qty': order.qty,
                                                'order_type': order_type,
                                                'status': order.status,
                                                'client_order_id': order.client_order_id
                                            }
                                            
                                            if save_option_order(order_data, client_user, prod):
                                                st.success("Order saved to database")
                                            else:
                                                st.warning("Order placed but not saved to database")
                                            
                                            # Add to session state
                                            st.session_state['option_orders'].append(order_details)
                                            
                                            # Log the test order for validation
                                            logger.info(f"TEST ORDER PLACED: {order_details}")
                                            st.info("📝 Test order logged for validation")
                                        else:
                                            st.error("Failed to place order")
                        else:
                            st.info("No suggestions available for the selected parameters")
                else:
                    st.warning("No options data available for the selected timeframe")
            else:
                st.error("Failed to fetch options chain")
    
    # Display recent orders
    if st.session_state['option_orders']:
        st.subheader("📋 Recent Option Orders")
        orders_df = pd.DataFrame(st.session_state['option_orders'])
        st.dataframe(orders_df, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Clear Orders"):
                st.session_state['option_orders'] = []
                st.rerun()
        with col2:
            if st.button("Refresh Orders"):
                # In a real implementation, you'd fetch from database
                st.info("Orders refreshed from session state")
    else:
        st.info("No option orders placed yet")

if __name__ == "__main__":
    main()
