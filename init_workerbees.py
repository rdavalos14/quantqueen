#!/usr/bin/env python3
"""
Initialize Worker Bees with proper ticker data
"""
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from chess_piece.queen_hive import init_swarm_dbs, init_qcp_workerbees
from chess_piece.king import PickleData, hive_master_root
import pandas as pd

def init_workerbees_tickers():
    """Initialize worker bees with default tickers"""
    
    # Default ticker configuration
    qcp_tickers = {
        'castle': ['SPY', 'QQQ', 'AAPL', 'MSFT'],
        'bishop': ['GOOG', 'META', 'NVDA', 'AMZN'], 
        'knight': ['TSLA', 'OXY', 'ADBE', 'NFLX']
    }
    
    # Initialize QUEENBEE structure
    QUEENBEE = {
        'workerbees': {}
    }
    
    # Create worker bee configurations
    for qcp, tickers in qcp_tickers.items():
        QUEENBEE['workerbees'][qcp] = init_qcp_workerbees(
            ticker_list=tickers,
            piece_name=qcp,
            buying_power=1.0
        )
        print(f"✅ Initialized {qcp} with tickers: {tickers}")
    
    # Save to database
    db_root = os.path.join(hive_master_root(), 'db')
    master_swarm_QUEENBEE_path = os.path.join(db_root, 'queen_App__sandbox.pkl')
    
    # Load existing data and update
    try:
        import pickle
        with open(master_swarm_QUEENBEE_path, 'rb') as f:
            existing_data = pickle.load(f)
    except:
        existing_data = {}
    
    existing_data['workerbees'] = QUEENBEE['workerbees']
    
    # Save updated data
    with open(master_swarm_QUEENBEE_path, 'wb') as f:
        pickle.dump(existing_data, f)
    
    print("✅ Worker bees initialized successfully!")
    print(f"📊 Total tickers configured: {sum(len(tickers) for tickers in qcp_tickers.values())}")
    
    return QUEENBEE

if __name__ == '__main__':
    init_workerbees_tickers()
